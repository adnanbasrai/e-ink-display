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

// Clear the saved network (forces the portal on next boot, once combined with
// wifiMarkReprovision() -- see below -- so a leftover secrets.h dev fallback
// can't silently resurrect the old connection).
void wifiForget();

// IMPORTANT: GPIO0 ("BOOT") is the ESP32's hardware boot-mode-select pin,
// sampled by the chip's ROM at the *exact instant* of reset -- before any of
// our code runs. If it's held LOW right then, the chip drops into the USB
// flashing bootloader instead of running the app at all (silently -- the
// e-ink panel just keeps showing whatever was last drawn, which looks
// exactly like "nothing happened"). So the button must NEVER be read at
// boot/reset time; the safe pattern is: watch it during NORMAL running
// (long after boot-mode selection is long over), and if a request is
// detected, wait for the button to be RELEASED before ever restarting.

// Call from loop() (frequently -- e.g. inside existing polling delays, not
// just once per minute) to detect a ~3s hold of the BOOT button during
// normal operation. On a long-press it blocks waiting for release, marks a
// persistent reprovision request, forgets the saved network, and restarts --
// so this call does not return once a long-press fires.
void wifiPollReprovisionButton(WifiStatusFn onStatus = nullptr);

// Checked once in setup(): true if wifiPollReprovisionButton() requested a
// re-provision on the previous run. Consumes (clears) the flag.
bool wifiConsumeReprovisionFlag();
