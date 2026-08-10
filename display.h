#pragma once
#include <time.h>
#include "gtfs_rt.h"
#include "weather.h"

// Render the whole board into the Paint framebuffer (Paint_NewImage must have
// been called first). Five equal columns: weather on the far left, then one
// column per ColumnConfig (bullet with route label, station name, next train
// in big digits, three more arrivals below -- plain numbers, no "min").
// Columns with no upcoming trains show a dash + "no service", and the ticker
// line at the bottom explains why (MTA alert blurb when one exists); with
// several such columns the ticker cycles by `rotation` (pass the refresh
// counter). `clock12` is the current time string shown bottom-right.
void displayRender(const RouteArrivals* routes, size_t nRoutes, time_t now,
                   const RouteAlert* alerts, const WeatherInfo& wx,
                   int rotation, const char* clock12);
