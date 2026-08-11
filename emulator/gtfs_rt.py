"""Minimal hand-rolled GTFS-realtime (protobuf wire format) reader.

A faithful Python port of the firmware's gtfs_rt.cpp. We only descend into the
handful of fields we care about and skip everything else, so no protobuf
library or generated code is needed -- exactly like on the ESP32.

Field numbers (gtfs-realtime.proto):
  FeedMessage.entity            = 2  (len)
  FeedEntity.trip_update        = 3  (len)
  FeedEntity.alert              = 5  (len)
  TripUpdate.trip               = 1  (len, TripDescriptor)
  TripUpdate.stop_time_update   = 2  (len, repeated StopTimeUpdate)
  TripDescriptor.route_id       = 5  (len, string)
  StopTimeUpdate.arrival        = 2  (len, StopTimeEvent)
  StopTimeUpdate.departure      = 3  (len, StopTimeEvent)
  StopTimeUpdate.stop_id        = 4  (len, string)
  StopTimeEvent.time            = 2  (varint, unix epoch seconds)
  Alert.active_period           = 1  (len, repeated TimeRange)
  Alert.informed_entity         = 5  (len, repeated EntitySelector)
  Alert.header_text             = 10 (len, TranslatedString)
  TimeRange.start / .end        = 1 / 2 (varint)
  EntitySelector.route_id       = 2  (len, string)
  TranslatedString.translation  = 1  (len); Translation.text = 1, .language = 2
"""

MAX_ARRIVALS = 12


class RouteArrivals:
    """Collected arrivals for one route at one stop (times = epoch seconds)."""

    def __init__(self, route, stop_id):
        self.route = route
        self.stop_id = stop_id
        self.times = []  # unix epoch seconds, sorted ascending, deduped
        self.dests = []  # terminal stop_id per arrival, aligned with times

    def insert_sorted(self, t, dest=""):
        if t in self.times:
            return  # a trip occasionally appears twice in a feed
        lo = 0
        while lo < len(self.times) and self.times[lo] < t:
            lo += 1
        self.times.insert(lo, t)
        self.dests.insert(lo, dest)
        if len(self.times) > MAX_ARRIVALS:
            del self.times[MAX_ARRIVALS:]
            del self.dests[MAX_ARRIVALS:]


class RouteAlert:
    """One service-alert blurb per route (MTA's short header, first line)."""

    def __init__(self, route):
        self.route = route
        self.text = ""


class _Cursor:
    __slots__ = ("buf", "p", "end")

    def __init__(self, buf, p, end):
        self.buf = buf
        self.p = p
        self.end = end


def _read_varint(c):
    """Return (value, ok). Advances c.p past the varint."""
    out = 0
    shift = 0
    while shift < 64:
        if c.p >= c.end:
            return 0, False
        b = c.buf[c.p]
        c.p += 1
        out |= (b & 0x7F) << shift
        if not (b & 0x80):
            return out, True
        shift += 7
    return 0, False  # varint too long


def _skip_field(c, wire):
    if wire == 0:  # varint
        _, ok = _read_varint(c)
        return ok
    if wire == 1:  # 64-bit
        if c.end - c.p < 8:
            return False
        c.p += 8
        return True
    if wire == 2:  # length-delimited
        v, ok = _read_varint(c)
        if not ok or (c.end - c.p) < v:
            return False
        c.p += v
        return True
    if wire == 5:  # 32-bit
        if c.end - c.p < 4:
            return False
        c.p += 4
        return True
    return False  # groups (3/4) never appear in GTFS-rt


def _enter(c):
    """Enter a length-delimited submessage; return (sub_cursor, ok)."""
    length, ok = _read_varint(c)
    if not ok or (c.end - c.p) < length:
        return None, False
    sub = _Cursor(c.buf, c.p, c.p + length)
    c.p += length
    return sub, True


def _read_string(c):
    length, ok = _read_varint(c)
    if not ok or (c.end - c.p) < length:
        return None, False
    s = c.buf[c.p:c.p + length]
    c.p += length
    try:
        return s.decode("utf-8", "replace"), True
    except Exception:
        return "", True


# ---- Trip updates (arrivals) ----

def _parse_stop_time_event(c):
    """StopTimeEvent -> epoch seconds (0 if absent)."""
    t = 0
    while c.p < c.end:
        tag, ok = _read_varint(c)
        if not ok:
            break
        if (tag >> 3) == 2 and (tag & 7) == 0:  # time
            v, ok = _read_varint(c)
            if not ok:
                return t
            t = v
        elif not _skip_field(c, tag & 7):
            return t
    return t


def _parse_stop_time_update(c):
    """Return (stop_id, arrival, departure)."""
    stop_id, arrival, departure = "", 0, 0
    while c.p < c.end:
        tag, ok = _read_varint(c)
        if not ok:
            break
        field, wire = tag >> 3, tag & 7
        if field == 4 and wire == 2:
            stop_id, ok = _read_string(c)
            if not ok:
                break
        elif field in (2, 3) and wire == 2:
            sub, ok = _enter(c)
            if not ok:
                break
            t = _parse_stop_time_event(sub)
            if field == 2:
                arrival = t
            else:
                departure = t
        elif not _skip_field(c, wire):
            break
    return stop_id, arrival, departure


def _parse_trip_update(c, routes_by_key):
    route_id = ""
    pending = []  # (stop_id, arrival, departure)
    while c.p < c.end:
        tag, ok = _read_varint(c)
        if not ok:
            return
        field, wire = tag >> 3, tag & 7
        if field == 1 and wire == 2:  # TripDescriptor
            td, ok = _enter(c)
            if not ok:
                return
            while td.p < td.end:
                t2, ok = _read_varint(td)
                if not ok:
                    break
                if (t2 >> 3) == 5 and (t2 & 7) == 2:  # route_id
                    route_id, ok = _read_string(td)
                    if not ok:
                        break
                elif not _skip_field(td, t2 & 7):
                    break
        elif field == 2 and wire == 2:  # StopTimeUpdate
            su, ok = _enter(c)
            if not ok:
                return
            stop_id, arr, dep = _parse_stop_time_update(su)
            if stop_id:
                pending.append((stop_id, arr, dep))
        elif not _skip_field(c, wire):
            return

    if not route_id:
        return
    # The trip's stop_time_updates run in stop order, so the last one is the
    # terminal -- where this train is going.
    terminal = pending[-1][0] if pending else ""
    for (route, stop_id), ra in routes_by_key.items():
        if route != route_id:
            continue
        for (sid, arr, dep) in pending:
            if sid != stop_id:
                continue
            t = arr if arr else dep
            if t:
                ra.insert_sorted(t, terminal)


def gtfs_rt_parse(buf, routes):
    """Parse a FeedMessage; append arrivals into the given RouteArrivals list."""
    routes_by_key = {(r.route, r.stop_id): r for r in routes}
    c = _Cursor(buf, 0, len(buf))
    while c.p < c.end:
        tag, ok = _read_varint(c)
        if not ok:
            return False
        field, wire = tag >> 3, tag & 7
        if field == 2 and wire == 2:  # FeedEntity
            entity, ok = _enter(c)
            if not ok:
                return False
            while entity.p < entity.end:
                t2, ok = _read_varint(entity)
                if not ok:
                    return False
                if (t2 >> 3) == 3 and (t2 & 7) == 2:  # trip_update
                    tu, ok = _enter(entity)
                    if not ok:
                        return False
                    _parse_trip_update(tu, routes_by_key)
                elif not _skip_field(entity, t2 & 7):
                    return False
        elif not _skip_field(c, wire):
            return False
    return True


# ---- Service alerts ----

def _parse_translated(c):
    """Pick the English translation (or the first) out of a TranslatedString."""
    out = ""
    have = False
    while c.p < c.end:
        tag, ok = _read_varint(c)
        if not ok:
            return out
        if (tag >> 3) == 1 and (tag & 7) == 2:  # translation
            tr, ok = _enter(c)
            if not ok:
                return out
            txt, lang = "", ""
            while tr.p < tr.end:
                t2, ok = _read_varint(tr)
                if not ok:
                    break
                if (t2 >> 3) == 1 and (t2 & 7) == 2:
                    txt, ok = _read_string(tr)
                    if not ok:
                        break
                elif (t2 >> 3) == 2 and (t2 & 7) == 2:
                    lang, ok = _read_string(tr)
                    if not ok:
                        break
                elif not _skip_field(tr, t2 & 7):
                    break
            if txt and (not have or lang == "en"):
                out = txt
                have = True
                if lang == "en":
                    return out
        elif not _skip_field(c, tag & 7):
            return out
    return out


def _parse_alert(c, now, alerts):
    matched = [False] * len(alerts)
    active = False
    any_period = False
    header = ""
    while c.p < c.end:
        tag, ok = _read_varint(c)
        if not ok:
            return
        field, wire = tag >> 3, tag & 7
        if field == 1 and wire == 2:  # TimeRange (active_period)
            any_period = True
            tr, ok = _enter(c)
            if not ok:
                return
            start, end = 0, 0
            while tr.p < tr.end:
                t2, ok = _read_varint(tr)
                if not ok:
                    break
                if (t2 >> 3) == 1 and (t2 & 7) == 0:
                    start, ok = _read_varint(tr)
                    if not ok:
                        break
                elif (t2 >> 3) == 2 and (t2 & 7) == 0:
                    end, ok = _read_varint(tr)
                    if not ok:
                        break
                elif not _skip_field(tr, t2 & 7):
                    break
            if (not start or start <= now) and (not end or end >= now):
                active = True
        elif field == 5 and wire == 2:  # EntitySelector (informed_entity)
            es, ok = _enter(c)
            if not ok:
                return
            while es.p < es.end:
                t2, ok = _read_varint(es)
                if not ok:
                    break
                if (t2 >> 3) == 2 and (t2 & 7) == 2:  # route_id
                    route_id, ok = _read_string(es)
                    if not ok:
                        break
                    for i, a in enumerate(alerts):
                        if a.route == route_id:
                            matched[i] = True
                elif not _skip_field(es, t2 & 7):
                    break
        elif field == 10 and wire == 2:  # header_text
            hd, ok = _enter(c)
            if not ok:
                return
            header = _parse_translated(hd)
        elif not _skip_field(c, wire):
            return

    if not header or (any_period and not active):
        return
    # Keep only the first line of multi-line headers.
    for sep in ("\n", "\r"):
        idx = header.find(sep)
        if idx >= 0:
            header = header[:idx]
    for i, a in enumerate(alerts):
        if matched[i] and not a.text:
            a.text = header


def gtfs_alerts_parse(buf, now, alerts):
    """Parse a service-alerts FeedMessage into the given RouteAlert list."""
    c = _Cursor(buf, 0, len(buf))
    while c.p < c.end:
        tag, ok = _read_varint(c)
        if not ok:
            return False
        field, wire = tag >> 3, tag & 7
        if field == 2 and wire == 2:  # FeedEntity
            entity, ok = _enter(c)
            if not ok:
                return False
            while entity.p < entity.end:
                t2, ok = _read_varint(entity)
                if not ok:
                    return False
                if (t2 >> 3) == 5 and (t2 & 7) == 2:  # alert
                    al, ok = _enter(entity)
                    if not ok:
                        return False
                    _parse_alert(al, now, alerts)
                elif not _skip_field(entity, t2 & 7):
                    return False
        elif not _skip_field(c, wire):
            return False
    return True
