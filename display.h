#pragma once
#include <time.h>
#include "gtfs_rt.h"
#include "weather.h"

// Render the whole board into the Paint framebuffer (Paint_NewImage must have
// been called first), in whichever style the fetched config selects:
//
//   'R'  Refined Signage -- weather column, then one framed column per route
//        (bullet + destination + big next arrival + follow-ups).
//   'H'  Hero Digit      -- weather compressed to a top strip, then one
//        oversized minutes number per column.
//   'P'  Platform Cards  -- each line on its own bordered card.
//
// All three show the same data: columns with no upcoming trains get a dash +
// "no service", and the bottom ticker explains why (the MTA alert blurb when
// one exists), cycling by `rotation` when several columns are out. `clock12`
// is the current time string and `date_str` the day+date, both bottom-right.
// The layout is read from the runtime config global LAYOUT.
void displayRender(const RouteArrivals* routes, size_t nRoutes, time_t now,
                   const RouteAlert* alerts, const WeatherInfo& wx,
                   int rotation, const char* clock12, int ebikes,
                   const char* date_str = "");
