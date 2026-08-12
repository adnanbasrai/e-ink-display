#pragma once
#include <Arduino.h>

// Self-serve WiFi setup: if the board has no working saved network, it starts
// its own WiFi hotspot ("SubwayBoard-XXXX") with a captive-portal setup page,
// so a friend can join it from their phone and pick their own home WiFi --
// no laptop, no re-flash, no touching secrets.h.

// Callback used to show two lines of status on the e-ink panel during setup
// (board_main.cpp passes its splash() function).
typedef void (*WifiStatusFn)(const char* line1, const char* line2);

// Short stable hotspot name derived from the chip's MAC, e.g. "SubwayBoard-DA5C".
String wifiApSsid();

// True if a network is saved (NVS, or secrets.h's WIFI_SSID as a dev fallback),
// regardless of whether it's reachable right now.
bool wifiHasStoredCreds();

// Try connecting with the saved network. Returns true if connected within
// timeoutMs.
bool wifiTryStored(uint32_t timeoutMs);

// Run the self-serve setup portal: starts the hotspot + captive portal page
// where a phone can pick a network and enter its password, blocks until a
// working network is saved, then restarts the board onto it. `onStatus`
// (optional) updates the e-ink screen with the hotspot name and progress.
void wifiRunPortal(WifiStatusFn onStatus = nullptr);

// Clear the saved network (forces the portal on next boot). Used when the
// BOOT button is held at power-on to re-provision (e.g. the password changed).
void wifiForget();
