// The editor SPA, served by the Worker at / and /edit.
//
// Design language: the portal is dressed as transit signage rather than as a
// generic dashboard, because the product already speaks that language -- the
// panel renders in Helvetica (the MTA's typeface since the 1970 Vignelli
// standards manual) and draws real MTA route bullets. So: a black station-sign
// masthead, uppercase micro-labels, monospace for identifiers (an equipment
// tag), hairline-ruled fieldsets, and colour reserved almost entirely for the
// route bullets, where the hue is the line's actual identity and not decoration.

import { NYC_SKYLINE, NYC_CREDIT } from "./bg.js";

export const EDITOR_HTML = `<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#0C0F16">
<title>SubwayBoard — Board Settings</title>
<style>
  :root{
    --ink:#0C0F16;            /* near-black, very slightly blue */
    --ink-2:#3A424F;          /* secondary text */
    --steel:#6B7482;          /* tertiary / micro-labels */
    --paper:#F4F2ED;          /* warm municipal off-white */
    --card:#FFFFFF;
    --navy:#14346B;           /* NYC institutional blue */
    --rule:rgba(12,15,22,.14);
    --rule-2:rgba(12,15,22,.08);
    --good:#0A7D3C;
    --bad:#B3261E;
    --sans:"Helvetica Neue",Helvetica,Arial,"Liberation Sans",sans-serif;
    --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
    --shadow:0 1px 2px rgba(12,15,22,.05), 0 12px 32px -12px rgba(12,15,22,.18);
  }
  *{box-sizing:border-box}
  html,body{margin:0;padding:0}
  body{
    background:var(--paper); color:var(--ink); font-family:var(--sans);
    font-size:15px; line-height:1.5; -webkit-font-smoothing:antialiased;
    text-rendering:optimizeLegibility;
  }
  ::selection{background:var(--navy); color:#fff}
  button,input,select{font:inherit; color:inherit}
  :focus-visible{outline:2px solid var(--navy); outline-offset:2px}

  /* ---------- shared type ---------- */
  .micro{
    font-size:10.5px; font-weight:700; letter-spacing:.13em; text-transform:uppercase;
    color:var(--steel);
  }
  .mono{font-family:var(--mono); font-variant-numeric:tabular-nums}

  /* ---------- full-bleed NYC backdrop (sign-in + boot) ---------- */
  .scene{
    position:fixed; inset:0; z-index:50; display:flex; align-items:center;
    justify-content:center; padding:24px; overflow:hidden;
    background:#0A0F18;
  }
  .scene::before{
    content:""; position:absolute; inset:0;
    background-image:url("${NYC_SKYLINE}");
    background-size:cover; background-position:center 62%;
    transform:scale(1.06);
    animation:drift 42s ease-in-out infinite alternate;
  }
  /* Scrim: navy-tinted rather than neutral black, and kept light enough in the
     middle band that the skyline stays legibly *blue* -- crushed to grey it
     stops reading as New York and becomes any dark photo. */
  .scene::after{
    content:""; position:absolute; inset:0;
    background:
      linear-gradient(180deg, rgba(8,16,34,.72) 0%, rgba(8,16,34,.20) 46%, rgba(6,12,26,.82) 100%),
      radial-gradient(130% 95% at 50% 48%, rgba(8,16,34,0) 34%, rgba(6,12,26,.55) 100%);
  }
  @keyframes drift{from{transform:scale(1.06) translate3d(-1.2%,0,0)}
                   to{transform:scale(1.10) translate3d(1.2%,-1%,0)}}
  @media (prefers-reduced-motion:reduce){.scene::before{animation:none}}
  .scene > *{position:relative; z-index:1}
  /* Editorial frame: brand pinned top-left, a standfirst bottom-left and the
     credit bottom-right, so the photograph is composed into rather than just
     sat on top of. */
  .frame{position:absolute; inset:0; z-index:2; pointer-events:none;
    padding:22px 24px; display:flex; flex-direction:column; justify-content:space-between}
  .frame .top{display:flex; align-items:center; gap:10px}
  .frame .bottom{display:flex; align-items:flex-end; justify-content:space-between; gap:20px}
  .frame .bullet{width:26px;height:26px;font-size:13px}
  .frame .wm{font-size:13px;font-weight:700;letter-spacing:-.01em;color:#fff;line-height:1}
  .frame .wm span{display:block;font-size:8.5px;font-weight:600;letter-spacing:.16em;
    text-transform:uppercase;color:rgba(255,255,255,.55);margin-top:3px}
  .standfirst{
    font-size:12px; letter-spacing:.02em; color:rgba(255,255,255,.66); max-width:30ch;
    line-height:1.5; text-wrap:pretty;
  }
  .credit{
    font-size:9px; letter-spacing:.1em; text-transform:uppercase;
    color:rgba(255,255,255,.38); text-align:right; flex:none;
  }
  @media (max-width:640px){ .standfirst{display:none} }

  /* ---------- sign-in ---------- */
  .signin{width:min(390px,100%); color:#fff}
  .signin .mark{display:flex; align-items:center; gap:11px; margin-bottom:26px}
  .bullet{
    width:38px;height:38px;border-radius:50%;background:#fff;color:#0C0F16;
    display:grid;place-items:center;font-weight:700;font-size:19px;flex:none;
    letter-spacing:-.02em;
  }
  .signin .wordmark{font-size:19px;font-weight:700;letter-spacing:-.015em;line-height:1.15}
  .signin .wordmark span{display:block;font-size:10.5px;font-weight:600;
    letter-spacing:.15em;text-transform:uppercase;color:rgba(255,255,255,.58);margin-top:3px}
  .signin h1{font-size:29px;font-weight:700;letter-spacing:-.022em;margin:0 0 8px;line-height:1.12}
  .signin p.lede{font-size:14px;color:rgba(255,255,255,.74);margin:0 0 26px;max-width:44ch;
    text-wrap:pretty}
  .panel{
    background:rgba(255,255,255,.055); border:1px solid rgba(255,255,255,.14);
    border-radius:3px; padding:20px; backdrop-filter:blur(14px) saturate(120%);
    -webkit-backdrop-filter:blur(14px) saturate(120%);
  }
  .panel .micro{color:rgba(255,255,255,.62)}
  .field{margin-bottom:14px}
  .field:last-of-type{margin-bottom:0}
  .field label{display:block; margin-bottom:6px}
  .field .hint{font-size:11.5px;color:rgba(255,255,255,.45);text-transform:none;
    letter-spacing:0;font-weight:400;margin-left:6px}
  .signin input{
    width:100%; background:rgba(6,10,18,.55); border:1px solid rgba(255,255,255,.2);
    border-radius:2px; padding:11px 13px; color:#fff; font-family:var(--mono);
    font-size:16px; letter-spacing:.06em;
  }
  .signin input::placeholder{color:rgba(255,255,255,.3); letter-spacing:.04em}
  .signin input:focus{border-color:#fff; background:rgba(6,10,18,.72)}
  .btn{
    display:inline-flex;align-items:center;justify-content:center;gap:8px;
    border:1px solid var(--ink); background:var(--ink); color:#fff;
    border-radius:2px; padding:11px 20px; font-size:13.5px; font-weight:700;
    letter-spacing:.05em; text-transform:uppercase; cursor:pointer; white-space:nowrap;
    transition:background .14s,color .14s,border-color .14s,opacity .14s;
  }
  .btn:hover{background:#232b38}
  .btn:disabled{opacity:.5;cursor:default}
  .btn-light{background:#fff;color:var(--ink);border-color:#fff;width:100%;margin-top:18px}
  .btn-light:hover{background:rgba(255,255,255,.88)}
  .btn-ghost{background:transparent;color:var(--ink);border-color:var(--rule)}
  .btn-ghost:hover{background:rgba(12,15,22,.05)}
  .msg{font-size:12.5px;min-height:17px;margin-top:11px;letter-spacing:.01em}
  .msg.err{color:#FF9C93}
  .msg.ok{color:#8FE0AE}

  /* boot splash */
  .boot{display:flex;flex-direction:column;align-items:center;gap:16px;color:#fff}
  .boot .bars{display:flex;gap:5px}
  .boot .bars i{width:3px;height:26px;background:rgba(255,255,255,.85);display:block;
    animation:pulse 1.05s ease-in-out infinite}
  .boot .bars i:nth-child(2){animation-delay:.12s}
  .boot .bars i:nth-child(3){animation-delay:.24s}
  .boot .bars i:nth-child(4){animation-delay:.36s}
  @keyframes pulse{0%,100%{transform:scaleY(.35);opacity:.45}50%{transform:scaleY(1);opacity:1}}
  @media (prefers-reduced-motion:reduce){.boot .bars i{animation:none;transform:scaleY(.7)}}

  /* ---------- masthead ---------- */
  .mast{position:sticky; top:0; z-index:30; background:var(--ink); color:#fff}
  /* A rule in the actual colours of the lines this board is showing. The
     decoration is derived from the configuration rather than applied to it,
     so it changes as you add or swap trains. */
  .stripe{display:flex; height:3px; background:var(--ink)}
  .stripe i{flex:1; display:block}
  .mast-in{
    max-width:1080px;margin:0 auto;padding:12px 22px;
    display:flex;align-items:center;gap:14px;
  }
  .mast .bullet{width:30px;height:30px;font-size:15px}
  .mast .title{font-size:14.5px;font-weight:700;letter-spacing:-.01em;line-height:1.1}
  .mast .title span{display:block;font-size:9.5px;font-weight:600;letter-spacing:.15em;
    text-transform:uppercase;color:rgba(255,255,255,.5);margin-top:2px}
  .mast .spacer{flex:1}
  .unit{
    display:flex;align-items:center;gap:9px;padding:5px 11px;
    border:1px solid rgba(255,255,255,.22); border-radius:2px;
  }
  .unit .k{font-size:9px;font-weight:700;letter-spacing:.13em;color:rgba(255,255,255,.5)}
  .unit .v{font-family:var(--mono);font-size:12.5px;letter-spacing:.06em}
  .mast button{
    background:none;border:0;color:rgba(255,255,255,.66);cursor:pointer;
    font-size:10.5px;font-weight:700;letter-spacing:.13em;text-transform:uppercase;padding:6px;
  }
  .mast button:hover{color:#fff}

  /* ---------- page ---------- */
  main{max-width:1080px;margin:0 auto;padding:26px 22px 132px}

  /* preview plate */
  .plate{margin-bottom:34px}
  .plate-head{display:flex;align-items:baseline;gap:12px;margin-bottom:9px}
  .plate-head .t{font-size:12px;font-weight:700;letter-spacing:.1em;text-transform:uppercase}
  .plate-head .d{font-size:11px;color:var(--steel);letter-spacing:.02em}
  .flip{display:flex;gap:0;margin-bottom:9px;border:1px solid var(--rule);
    border-radius:2px;overflow:hidden;width:fit-content;background:var(--card)}
  .flip button{
    display:flex;align-items:center;gap:7px;background:none;border:0;cursor:pointer;
    padding:8px 14px;font-size:11px;font-weight:700;letter-spacing:.1em;
    text-transform:uppercase;color:var(--steel);
    border-right:1px solid var(--rule);
  }
  .flip button:last-child{border-right:0}
  .flip button:hover{background:#EFF2F7;color:var(--ink-2)}
  .flip button.on{background:var(--ink);color:#fff}
  .flip .dot{width:6px;height:6px;border-radius:50%;background:currentColor;flex:none;opacity:.5}
  .flip .dot.live{background:var(--good);opacity:1}
  .flip button.on .dot.live{background:#4ADE80}
  .flip .rev{font-size:10px;letter-spacing:.06em;opacity:.65;font-weight:400}
  .bezel{
    background:linear-gradient(180deg,#2A2F38,#1B1F26); padding:11px; border-radius:5px;
    box-shadow:var(--shadow);
  }
  .glass{
    position:relative; background:#fff; border-radius:1px; overflow:hidden;
    box-shadow:inset 0 0 0 1px rgba(12,15,22,.22); aspect-ratio:792/272;
  }
  .glass img{display:block;width:100%;height:100%;object-fit:contain;image-rendering:pixelated}
  .glass img[hidden]{display:none}   /* display:block above would otherwise beat [hidden] */
  /* loading state over the panel: the NYC photo, scrimmed, with a status line */
  .glass .load{
    position:absolute; inset:0; display:none; place-items:center;
    background-image:url("${NYC_SKYLINE}"); background-size:cover; background-position:center 60%;
  }
  .glass.busy .load{display:grid}
  .glass .load::before{content:"";position:absolute;inset:0;background:rgba(8,13,22,.72)}
  .glass .load b{
    position:relative;color:#fff;font-size:10px;font-weight:700;letter-spacing:.2em;
    text-transform:uppercase;display:flex;align-items:center;gap:9px;
  }
  .glass .load i{width:3px;height:13px;background:#fff;display:block;
    animation:pulse 1.05s ease-in-out infinite}
  .glass .load i:nth-child(2){animation-delay:.12s}
  .glass .load i:nth-child(3){animation-delay:.24s}
  .glass.empty{display:grid;place-items:center}
  .glass.empty::after{
    content:"No preview yet"; font-size:11px; letter-spacing:.1em; text-transform:uppercase;
    color:#9AA2AE;
  }

  /* ---------- fieldsets ---------- */
  .set{border-top:1px solid var(--rule); padding:22px 0}
  .set:last-of-type{border-bottom:1px solid var(--rule)}
  .set-head{display:flex;align-items:baseline;gap:11px;margin-bottom:14px}
  .set-head h2{font-size:13px;font-weight:700;letter-spacing:.02em;margin:0}
  .set-head .note{font-size:12px;color:var(--steel)}
  .row{display:grid;grid-template-columns:170px 1fr;gap:18px;align-items:start}
  @media (max-width:640px){.row{grid-template-columns:1fr;gap:7px}}
  .row + .row{margin-top:16px}
  .row .lab{padding-top:9px}
  .row .lab .sub{display:block;font-size:11px;font-weight:400;letter-spacing:0;
    text-transform:none;color:var(--steel);margin-top:3px;line-height:1.35}

  .inp{
    width:100%; background:var(--card); border:1px solid var(--rule);
    border-radius:2px; padding:10px 12px; font-size:14.5px;
  }
  .inp:hover{border-color:rgba(12,15,22,.26)}
  .inp:focus{border-color:var(--navy);box-shadow:0 0 0 3px rgba(20,52,107,.1);outline:none}
  select.inp{appearance:none;background-image:
    linear-gradient(45deg,transparent 50%,var(--ink-2) 50%),
    linear-gradient(135deg,var(--ink-2) 50%,transparent 50%);
    background-position:calc(100% - 17px) 50%,calc(100% - 12px) 50%;
    background-size:5px 5px,5px 5px;background-repeat:no-repeat;padding-right:34px}
  .pick{display:flex;align-items:center;gap:7px;font-size:12.5px;color:var(--good);
    margin-top:6px;min-height:17px}
  .pick svg{flex:none}
  .pick .none{color:var(--steel)}

  /* autocomplete */
  .ac{position:relative}
  .ac-list{
    position:absolute;z-index:20;left:0;right:0;top:calc(100% + 3px);background:var(--card);
    border:1px solid var(--rule);border-radius:2px;box-shadow:var(--shadow);
    max-height:246px;overflow-y:auto;
  }
  .ac-list button{
    display:flex;width:100%;align-items:center;gap:10px;text-align:left;background:none;
    border:0;border-bottom:1px solid var(--rule-2);padding:9px 12px;cursor:pointer;font-size:13.5px;
  }
  .ac-list button:last-child{border-bottom:0}
  .ac-list button:hover,.ac-list button.on{background:#EFF2F7}
  .ac-list .nm{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .lines{display:flex;gap:3px;flex:none}

  /* route bullet: the one place colour earns its keep -- these are the MTA's
     own line colours, so the hue is the line's identity, not decoration. */
  .rb{
    width:20px;height:20px;border-radius:50%;display:grid;place-items:center;
    font-size:11px;font-weight:700;color:#fff;flex:none;letter-spacing:-.01em;
  }
  .rb.lt{color:#0C0F16}
  .rb.sm{width:17px;height:17px;font-size:9.5px}

  /* Commuter-rail branches are named, not lettered, so they get a bar rather
     than a circle -- the same distinction the panel draws, and the same one the
     MTA makes on its own signage. */
  .rr{
    display:inline-grid;place-items:center;height:18px;padding:0 6px;border-radius:2px;
    font-size:9px;font-weight:700;color:#fff;letter-spacing:.04em;white-space:nowrap;
  }

  /* trains */
  .train{display:flex;align-items:center;gap:10px;margin-bottom:9px;flex-wrap:wrap}
  /* A rail row needs an origin as well as a destination -- your Metro-North
     station is rarely the subway stop outside your door -- so it wraps onto a
     second line rather than squeezing four controls into one. */
  .train.rail .sel{width:126px}
  /* The bar already names the branch, so the select's own text would only
     repeat it -- and at this width it repeats it truncated ("Hud"). Hide the
     text and let the bar be the label, exactly as the bullet is for a subway
     line. The accessible name still comes from the option and the aria-label. */
  .train.rail .sel select{padding-left:12px;color:transparent}
  .train.rail .sel .rr{position:absolute;left:6px;top:50%;transform:translateY(-50%);
    pointer-events:none;max-width:96px;overflow:hidden}
  /* Indented to line up under the destination, so it reads as part of the row
     above rather than a field of its own. */
  .train .from{flex:1 1 100%;min-width:0;display:flex;align-items:center;gap:8px;
    margin:-3px 0 2px;padding-left:136px}
  .train .from label{
    flex:none;font-size:9.5px;letter-spacing:.1em;text-transform:uppercase;
    color:var(--steel);font-weight:700;
  }
  .train .from .ac{flex:1;min-width:0}
  /* 32px of left padding clears the bullet and the caret takes another 34px,
     which left the line letter about 8px to sit in. Wider, plus a tighter
     caret gutter, so the extra room actually goes to the content. */
  .train .sel{position:relative;flex:none;width:82px}
  .train .sel select{padding-left:33px;padding-right:24px;
    background-position:calc(100% - 13px) 50%,calc(100% - 8px) 50%}
  .train .sel .rb{position:absolute;left:7px;top:50%;transform:translateY(-50%);
    pointer-events:none;width:19px;height:19px;font-size:10.5px}
  .train .dest{flex:1;min-width:0}
  .train .x{
    flex:none;background:none;border:1px solid transparent;color:var(--steel);
    cursor:pointer;padding:7px 9px;border-radius:2px;line-height:1;font-size:15px;
  }
  .train .x:hover{color:var(--bad);border-color:var(--rule)}
  .add{
    background:none;border:1px dashed var(--rule);border-radius:2px;padding:9px 14px;
    cursor:pointer;font-size:12px;font-weight:700;letter-spacing:.09em;text-transform:uppercase;
    color:var(--ink-2);width:100%;
  }
  .add:hover{border-color:var(--navy);color:var(--navy)}
  .add:disabled{opacity:.45;cursor:default}

  /* board style cards */
  .styles{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
  @media (max-width:640px){.styles{grid-template-columns:1fr}}
  .styles button{
    background:var(--card);border:1px solid var(--rule);border-radius:2px;
    padding:12px;cursor:pointer;text-align:left;transition:border-color .14s,box-shadow .14s;
  }
  .styles button:hover{border-color:rgba(12,15,22,.3)}
  .styles button{position:relative}
  .styles button.on{border-color:var(--ink);box-shadow:inset 0 0 0 1px var(--ink)}
  .styles button.on .nm::after{
    content:"Selected"; float:right; font-size:9px; font-weight:700; letter-spacing:.11em;
    text-transform:uppercase; background:var(--ink); color:#fff; padding:2px 6px; border-radius:1px;
  }
  .styles .nm{font-size:13px;font-weight:700;margin-bottom:2px}
  .styles .ds{font-size:11.5px;color:var(--steel);line-height:1.35}
  .styles svg{display:block;width:100%;height:auto;margin-bottom:9px;
    background:#fff;box-shadow:inset 0 0 0 1px var(--rule)}

  /* ---------- action bar ---------- */
  .bar{
    position:fixed;left:0;right:0;bottom:0;z-index:25;background:rgba(244,242,237,.94);
    backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);
    border-top:1px solid var(--rule);
  }
  .bar-in{
    max-width:1080px;margin:0 auto;padding:12px 22px;display:flex;align-items:center;gap:12px;
  }
  .bar .status{flex:1;font-size:12.5px;color:var(--steel);min-height:17px}
  .bar .status.ok{color:var(--good)} .bar .status.err{color:var(--bad)}
  .hidden{display:none !important}

  /* ---------- narrow screens ---------- */
  @media (max-width:600px){
    main{padding:18px 16px 108px}
    .mast-in{padding:10px 16px;gap:10px}
    .mast .title span{display:none}          /* subtitle wraps and costs a line */
    .unit .k{display:none}                    /* the value alone is unambiguous */
    .unit{padding:4px 9px}
    .plate-head{flex-direction:column;gap:2px}
    .plate-head .d{font-size:10.5px}
    /* No room to indent the origin under the destination on a phone. */
    .train .from{padding-left:0}
    .flip button{padding:7px 10px;font-size:10px;letter-spacing:.07em;white-space:nowrap}
    .flip .rev{display:none}
    /* A 2.9:1 panel shrunk to a phone's width is unreadable, so let it keep a
       usable size and scroll sideways instead of scaling into illegibility. */
    .bezel{overflow-x:auto;-webkit-overflow-scrolling:touch}
    .glass{min-width:540px}
    .set{padding:18px 0}
    .bar-in{padding:10px 16px;gap:9px}
    .bar .status{flex-basis:100%;order:-1}
    .btn{padding:10px 14px;font-size:12.5px}
    .wide{display:none}                       /* "Save to board" -> "Save" */
  }
</style></head>
<body>

<!-- boot / sign-in scene ------------------------------------------------- -->
<div class="scene" id="scene">
  <div class="frame">
    <div class="top">
      <div class="bullet">S</div>
      <div class="wm">SubwayBoard<span>Board Settings</span></div>
    </div>
    <div class="bottom">
      <p class="standfirst">Live MTA arrivals on an e-ink panel by your door.<br>No app. No backlight.</p>
      <div class="credit">${NYC_CREDIT}</div>
    </div>
  </div>

  <div class="boot" id="boot">
    <div class="bars"><i></i><i></i><i></i><i></i></div>
    <div class="micro" style="color:rgba(255,255,255,.7)">Connecting</div>
  </div>

  <div class="signin hidden" id="signin">
    <h1>Sign in to your board.</h1>
    <p class="lede">Use the display ID and PIN shown on the board&rsquo;s screen.</p>
    <div class="panel">
      <div class="field">
        <label class="micro" for="displayId">Display ID <span class="hint">e.g. SB-4F2A</span></label>
        <input id="displayId" placeholder="SB-XXXX" autocomplete="off" autocapitalize="characters" spellcheck="false">
      </div>
      <div class="field">
        <label class="micro" for="pin">PIN <span class="hint">6 digits</span></label>
        <input id="pin" placeholder="000000" inputmode="numeric" autocomplete="off" maxlength="6">
      </div>
      <button class="btn btn-light" id="loginBtn">Sign in</button>
      <div class="msg" id="loginMsg" role="status" aria-live="polite"></div>
    </div>
  </div>
</div>

<!-- editor ---------------------------------------------------------------- -->
<div class="hidden" id="app">
  <header class="mast">
    <div class="mast-in">
      <div class="bullet">S</div>
      <div class="title">SubwayBoard<span>Board Settings</span></div>
      <div class="spacer"></div>
      <div class="unit"><span class="k">UNIT</span><span class="v" id="unitId">—</span></div>
      <button id="logoutBtn">Sign out</button>
    </div>
    <div class="stripe" id="stripe" aria-hidden="true"></div>
  </header>

  <main>
    <section class="plate">
      <div class="plate-head">
        <span class="t">Panel preview</span>
        <span class="d">792 &times; 272 &middot; 1-bit &middot; rendered with your live arrivals</span>
      </div>
      <!-- One panel with an A/B flip rather than two side by side: at this
           aspect ratio two-up is unreadable, and stacked they push every
           control below the fold. Flipping in place also makes small
           differences easier to spot than comparing across a gutter. -->
      <div class="flip" role="tablist" aria-label="Preview state">
        <button type="button" role="tab" id="tabNow" class="on" aria-selected="true">
          <span class="dot live"></span>On board now <span class="mono rev" id="revNow"></span>
        </button>
        <button type="button" role="tab" id="tabNext" aria-selected="false">
          <span class="dot"></span>After your changes
        </button>
      </div>
      <div class="bezel"><div class="glass empty" id="glass">
        <img id="boardImg" alt="Board preview" hidden>
        <div class="load"><b><i></i><i></i><i></i>&nbsp;Rendering</b></div>
      </div></div>
    </section>

    <section class="set">
      <div class="set-head"><h2>Board style</h2><span class="note">How the panel arranges what it shows.</span></div>
      <div class="styles" id="styles"></div>
    </section>

    <section class="set">
      <div class="set-head"><h2>Station &amp; trains</h2><span class="note">Where the board reads times, and which trains it lists.</span></div>
      <div class="row">
        <div class="lab micro">Home station<span class="sub">The stop the board reads arrival times at.</span></div>
        <div>
          <div class="ac"><input class="inp" id="home" placeholder="Search a subway station…" autocomplete="off">
            <div class="ac-list hidden" id="homeList"></div></div>
          <div class="pick" id="homePick"></div>
        </div>
      </div>
      <div class="row">
        <div class="lab micro">Trains<span class="sub">Pick a line and where it&rsquo;s heading. Up to four.</span></div>
        <div>
          <div id="trains"></div>
          <button class="add" id="addTrain">+ Add train</button>
        </div>
      </div>
    </section>

    <section class="set">
      <div class="set-head"><h2>Weather &amp; bikes</h2><span class="note">The left-hand column of the board.</span></div>
      <div class="row">
        <div class="lab micro">Weather location<span class="sub">Searched by address or place name.</span></div>
        <div>
          <div class="ac"><input class="inp" id="addr" placeholder="Search an address or place…" autocomplete="off">
            <div class="ac-list hidden" id="addrList"></div></div>
          <div class="pick" id="addrPick"></div>
        </div>
      </div>
      <div class="row">
        <div class="lab micro">Citi Bike station<span class="sub">Shows e-bikes available. Optional.</span></div>
        <div>
          <div class="ac"><input class="inp" id="cb" placeholder="Search a Citi Bike station…" autocomplete="off">
            <div class="ac-list hidden" id="cbList"></div></div>
          <div class="pick" id="cbPick"></div>
        </div>
      </div>
    </section>

    <section class="set">
      <div class="set-head"><h2>Board</h2><span class="note">Naming and refresh behaviour.</span></div>
      <div class="row">
        <div class="lab micro">Board name</div>
        <div><input class="inp" id="name" placeholder="My Board" maxlength="40"></div>
      </div>
      <div class="row">
        <div class="lab micro">Service alerts<span class="sub">How often to check for MTA alerts.</span></div>
        <div><select class="inp" id="alerts">
          <option value="5">Every 5 minutes</option>
          <option value="10">Every 10 minutes</option>
          <option value="15">Every 15 minutes</option>
          <option value="30">Every 30 minutes</option>
        </select></div>
      </div>
    </section>
  </main>

  <div class="bar">
    <div class="bar-in">
      <div class="status" id="status" role="status" aria-live="polite"></div>
      <button class="btn btn-ghost" id="previewBtn">Preview</button>
      <button class="btn" id="saveBtn">Save<span class="wide"> to board</span></button>
    </div>
  </div>
</div>

<script>
var $ = function(id){ return document.getElementById(id); };
var token = sessionStorage.getItem("sb_token");
var deviceId = sessionStorage.getItem("sb_device");
var edit = null;

// MTA line colours -- the bullet's hue is the line's identity.
var LINE_COLORS = {
  "1":"#EE352E","2":"#EE352E","3":"#EE352E",
  "4":"#00933C","5":"#00933C","6":"#00933C",
  "7":"#B933AD",
  "A":"#2850AD","C":"#2850AD","E":"#2850AD",
  "B":"#FF6319","D":"#FF6319","F":"#FF6319","M":"#FF6319",
  "N":"#FCCC0A","Q":"#FCCC0A","R":"#FCCC0A","W":"#FCCC0A",
  "G":"#6CBE45","J":"#996633","Z":"#996633",
  "L":"#A7A9AC","S":"#808183"
};
var LIGHT_LINES = {"N":1,"Q":1,"R":1,"W":1};   // yellow needs dark type
var LINES = ["1","2","3","4","5","6","7","A","C","E","B","D","F","M","N","Q","R","W","G","J","Z","L","S"];

// Commuter-rail branches. "s" is exactly what the board prints on its bar, so
// what you pick here is what you'll read across the room; "c" is each agency's
// official route_color from its static GTFS. Kept in step with RAIL_BRANCHES
// in config.js.
var RAIL = {
  L: { name:"LIRR", branches:[
    {r:"1",  s:"BABYLON",    n:"Babylon",         c:"#00985F"},
    {r:"2",  s:"HEMPSTEAD",  n:"Hempstead",       c:"#CE8E00"},
    {r:"3",  s:"OYSTER BAY", n:"Oyster Bay",      c:"#00AF3F"},
    {r:"4",  s:"RONKONKOMA", n:"Ronkonkoma",      c:"#A626AA"},
    {r:"5",  s:"MONTAUK",    n:"Montauk",         c:"#00B2A9"},
    {r:"6",  s:"LONG BEACH", n:"Long Beach",      c:"#FF6319"},
    {r:"7",  s:"FAR ROCK",   n:"Far Rockaway",    c:"#6E3219"},
    {r:"8",  s:"W HEMPSTD",  n:"West Hempstead",  c:"#00A1DE"},
    {r:"9",  s:"PORT WASH",  n:"Port Washington", c:"#C60C30"},
    {r:"10", s:"PORT JEFF",  n:"Port Jefferson",  c:"#006EC7"},
    {r:"11", s:"BELMONT",    n:"Belmont Park",    c:"#60269E"},
    {r:"12", s:"CITY ZONE",  n:"City Terminal",   c:"#4D5357"},
    {r:"13", s:"GREENPORT",  n:"Greenport",       c:"#A626AA"}
  ]},
  M: { name:"Metro-North", branches:[
    {r:"1", s:"HUDSON",     n:"Hudson",     c:"#009B3A"},
    {r:"2", s:"HARLEM",     n:"Harlem",     c:"#0039A6"},
    {r:"3", s:"NEW HAVEN",  n:"New Haven",  c:"#EE0034"},
    {r:"4", s:"NEW CANAAN", n:"New Canaan", c:"#EE0034"},
    {r:"5", s:"DANBURY",    n:"Danbury",    c:"#EE0034"},
    {r:"6", s:"WATERBURY",  n:"Waterbury",  c:"#EE0034"}
  ]}
};

function branchOf(col){
  var a = RAIL[col && col.agency];
  if (!a) return null;
  for (var i = 0; i < a.branches.length; i++)
    if (a.branches[i].r === String(col.line)) return a.branches[i];
  return null;
}

var STYLES = [
  { id:"R", name:"Refined", ds:"Five columns, framed. The classic board.",
    svg:'<rect x="1" y="1" width="130" height="44" fill="none" stroke="#0C0F16" stroke-width="2"/>'+
        '<line x1="27" y1="5" x2="27" y2="35" stroke="#0C0F16"/><line x1="53" y1="5" x2="53" y2="35" stroke="#0C0F16"/>'+
        '<line x1="79" y1="5" x2="79" y2="35" stroke="#0C0F16"/><line x1="105" y1="5" x2="105" y2="35" stroke="#0C0F16"/>'+
        '<circle cx="40" cy="14" r="6" fill="#0C0F16"/><circle cx="66" cy="14" r="6" fill="#0C0F16"/>'+
        '<circle cx="92" cy="14" r="6" fill="#0C0F16"/><circle cx="118" cy="14" r="6" fill="#0C0F16"/>'+
        '<text x="14" y="18" font-size="9" font-weight="700" text-anchor="middle" fill="#0C0F16">86°</text>'+
        '<text x="40" y="30" font-size="9" font-weight="700" text-anchor="middle" fill="#0C0F16">8</text>'+
        '<text x="66" y="30" font-size="9" font-weight="700" text-anchor="middle" fill="#0C0F16">2</text>'+
        '<text x="92" y="30" font-size="9" font-weight="700" text-anchor="middle" fill="#0C0F16">4</text>'+
        '<text x="118" y="30" font-size="9" font-weight="700" text-anchor="middle" fill="#0C0F16">0</text>'+
        '<line x1="5" y1="39" x2="127" y2="39" stroke="#0C0F16"/>' },
  { id:"H", name:"Hero digit", ds:"One big number per line. Reads across a room.",
    svg:'<rect x="1" y="1" width="130" height="44" fill="none" stroke="#0C0F16" stroke-width="2"/>'+
        '<rect x="4" y="10" width="124" height="3" fill="#0C0F16"/>'+
        '<text x="10" y="9" font-size="7" font-weight="700" fill="#0C0F16">86°</text>'+
        '<circle cx="14" cy="19" r="4" fill="#0C0F16"/><circle cx="47" cy="19" r="4" fill="#0C0F16"/>'+
        '<circle cx="80" cy="19" r="4" fill="#0C0F16"/><circle cx="113" cy="19" r="4" fill="#0C0F16"/>'+
        '<text x="21" y="35" font-size="17" font-weight="700" text-anchor="middle" fill="#0C0F16">8</text>'+
        '<text x="54" y="35" font-size="17" font-weight="700" text-anchor="middle" fill="#0C0F16">2</text>'+
        '<text x="87" y="35" font-size="17" font-weight="700" text-anchor="middle" fill="#0C0F16">4</text>'+
        '<text x="120" y="35" font-size="17" font-weight="700" text-anchor="middle" fill="#0C0F16">0</text>'+
        '<line x1="4" y1="40" x2="128" y2="40" stroke="#0C0F16"/>' },
  { id:"P", name:"Cards", ds:"Each line on its own bordered card.",
    svg:'<rect x="1" y="1" width="130" height="44" fill="none" stroke="#0C0F16" stroke-width="2"/>'+
        '<rect x="5" y="5" width="22" height="30" fill="none" stroke="#0C0F16" stroke-width="1.5"/>'+
        '<rect x="30" y="5" width="22" height="30" fill="none" stroke="#0C0F16" stroke-width="1.5"/>'+
        '<rect x="55" y="5" width="22" height="30" fill="none" stroke="#0C0F16" stroke-width="1.5"/>'+
        '<rect x="80" y="5" width="22" height="30" fill="none" stroke="#0C0F16" stroke-width="1.5"/>'+
        '<rect x="105" y="5" width="22" height="30" fill="none" stroke="#0C0F16" stroke-width="1.5"/>'+
        '<text x="16" y="24" font-size="9" font-weight="700" text-anchor="middle" fill="#0C0F16">86°</text>'+
        '<rect x="33" y="8" width="9" height="6" fill="#0C0F16"/><rect x="58" y="8" width="9" height="6" fill="#0C0F16"/>'+
        '<rect x="83" y="8" width="9" height="6" fill="#0C0F16"/><rect x="108" y="8" width="9" height="6" fill="#0C0F16"/>'+
        '<text x="35" y="30" font-size="12" font-weight="700" fill="#0C0F16">8</text>'+
        '<text x="60" y="30" font-size="12" font-weight="700" fill="#0C0F16">2</text>'+
        '<text x="85" y="30" font-size="12" font-weight="700" fill="#0C0F16">4</text>'+
        '<text x="110" y="30" font-size="12" font-weight="700" fill="#0C0F16">0</text>'+
        '<rect x="5" y="38" width="122" height="4" fill="none" stroke="#0C0F16"/>' }
];

function esc(s){ return String(s == null ? "" : s).replace(/[&<>"']/g, function(c){
  return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]; }); }

function bulletHTML(line, cls){
  var L = String(line || "").toUpperCase();
  var bg = LINE_COLORS[L] || "#0C0F16";
  return '<span class="rb ' + (LIGHT_LINES[L] ? "lt " : "") + (cls || "") +
         '" style="background:' + bg + '">' + esc(L) + '</span>';
}

var CHECK = '<svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">' +
            '<path d="M1.5 6.4 4.3 9.2 10.5 3" fill="none" stroke="currentColor" ' +
            'stroke-width="2" stroke-linecap="square"/></svg>';

function setPick(el, text){
  el.innerHTML = text ? (CHECK + "<span>" + esc(text) + "</span>")
                      : '<span class="none">Not set</span>';
}
function setMsg(el, text, kind){
  el.textContent = text || "";
  el.className = (el.id === "status" ? "status " : "msg ") + (kind || "");
}
function debounce(fn, ms){ var t; return function(){ var a = arguments;
  clearTimeout(t); t = setTimeout(function(){ fn.apply(null, a); }, ms || 220); }; }

// ---- sign in ----
function login(){
  setMsg($("loginMsg"), "", "");
  var btn = $("loginBtn"); btn.disabled = true;
  fetch("/api/login", { method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({ display_id: $("displayId").value.trim().toUpperCase(),
                           pin: $("pin").value.trim() }) })
    .then(function(r){ return r.json().then(function(j){ return { ok:r.ok, j:j }; }); })
    .then(function(res){
      btn.disabled = false;
      if (!res.ok){ setMsg($("loginMsg"), res.j.error || "Sign in failed", "err"); return; }
      token = res.j.token; deviceId = res.j.device_id;
      sessionStorage.setItem("sb_token", token);
      sessionStorage.setItem("sb_device", deviceId);
      sessionStorage.setItem("sb_display", res.j.display_id || "");
      start();
    })
    .catch(function(){ btn.disabled = false;
      setMsg($("loginMsg"), "Network error — try again", "err"); });
}
function logout(){
  token = deviceId = null; sessionStorage.clear();
  $("app").classList.add("hidden");
  $("scene").classList.remove("hidden");
  $("boot").classList.add("hidden");
  $("signin").classList.remove("hidden");
}

// ---- autocomplete ----
function autocomplete(input, list, endpoint, render, onPick){
  var items = [], cur = -1;
  var run = debounce(function(){
    var q = input.value.trim();
    if (q.length < 2){ list.classList.add("hidden"); return; }
    fetch(endpoint + encodeURIComponent(q))
      .then(function(r){ return r.json(); })
      .then(function(d){
        items = d.results || []; cur = -1;
        list.innerHTML = "";
        items.forEach(function(it, i){
          var b = document.createElement("button");
          b.type = "button";
          b.innerHTML = render(it);
          b.onmousedown = function(e){ e.preventDefault(); };
          b.onclick = function(){ list.classList.add("hidden"); onPick(it); };
          b.onmouseenter = function(){ cur = i; paint(); };
          list.appendChild(b);
        });
        list.classList.toggle("hidden", items.length === 0);
      })
      .catch(function(){ list.classList.add("hidden"); });
  });
  function paint(){
    var bs = list.querySelectorAll("button");
    for (var i = 0; i < bs.length; i++) bs[i].className = (i === cur ? "on" : "");
  }
  input.addEventListener("input", run);
  input.addEventListener("keydown", function(e){
    if (list.classList.contains("hidden")) return;
    if (e.key === "ArrowDown"){ e.preventDefault(); cur = Math.min(cur + 1, items.length - 1); paint(); }
    else if (e.key === "ArrowUp"){ e.preventDefault(); cur = Math.max(cur - 1, 0); paint(); }
    else if (e.key === "Enter" && cur >= 0){ e.preventDefault();
      list.classList.add("hidden"); onPick(items[cur]); }
    else if (e.key === "Escape"){ list.classList.add("hidden"); }
  });
  input.addEventListener("blur", function(){
    setTimeout(function(){ list.classList.add("hidden"); }, 140); });
}

function stationRow(s){
  var lines = String(s.routes || "").trim().split(/\\s+/).filter(Boolean);
  var b = lines.slice(0, 8).map(function(l){ return bulletHTML(l, "sm"); }).join("");
  return '<span class="nm">' + esc(s.name) + '</span><span class="lines">' + b + '</span>';
}

// ---- editor ----
function start(){
  $("scene").classList.add("hidden");
  $("app").classList.remove("hidden");
  // Show the human display ID (SB-XXXX), never the raw hardware id -- an older
  // session may predate us storing it, so fall back to asking the server.
  var shown = sessionStorage.getItem("sb_display");
  $("unitId").textContent = shown || "—";
  if (!shown){
    fetch("/api/config?device=" + encodeURIComponent(deviceId))
      .then(function(r){ return r.json(); })
      .then(function(c){
        if (c.display_id){
          sessionStorage.setItem("sb_display", c.display_id);
          $("unitId").textContent = c.display_id;
        }
      }).catch(function(){});
  }
  fetch("/api/devices/" + encodeURIComponent(deviceId) + "/edit",
        { headers:{ "Authorization":"Bearer " + token } })
    .then(function(r){ if (r.status === 401){ logout(); throw new Error("auth"); } return r.json(); })
    .then(function(d){
      edit = d.edit || {};
      if (!edit.columns) edit.columns = [];
      fillForm();
      renderBefore();
    })
    .catch(function(){});
}

function renderStyles(){
  var box = $("styles"); box.innerHTML = "";
  STYLES.forEach(function(s){
    var b = document.createElement("button");
    b.type = "button";
    b.className = (edit.layout || "R") === s.id ? "on" : "";
    b.setAttribute("aria-pressed", String((edit.layout || "R") === s.id));
    b.innerHTML = '<svg viewBox="0 0 132 46" aria-hidden="true">' + s.svg + '</svg>' +
                  '<div class="nm">' + esc(s.name) + '</div>' +
                  '<div class="ds">' + esc(s.ds) + '</div>';
    b.onclick = function(){ edit.layout = s.id; renderStyles(); doPreview(); };
    box.appendChild(b);
  });
}

// A rail station row in an autocomplete list, labelled with its branches.
function railRow(s){
  var a = RAIL[s.stop_id.charAt(0)];
  var rs = String(s.routes || "").trim().split(/\s+/).filter(Boolean);
  var b = rs.slice(0, 4).map(function(r){
    for (var i = 0; a && i < a.branches.length; i++)
      if (a.branches[i].r === r)
        return '<span class="rr" style="background:' + a.branches[i].c + '">' +
               esc(a.branches[i].s) + '</span>';
    return "";
  }).join(" ");
  return '<span class="nm">' + esc(s.name) + '</span><span class="lines">' + b + '</span>';
}

function renderTrains(){
  var box = $("trains"); box.innerHTML = "";
  edit.columns.forEach(function(col, i){
    var br = branchOf(col);
    var row = document.createElement("div");
    row.className = "train" + (br ? " rail" : "");

    // One control picks the service, subway and commuter rail together --
    // they're alternatives for the same slot on the board, not separate ideas.
    var sel = document.createElement("div"); sel.className = "sel";
    var s = document.createElement("select"); s.className = "inp";
    s.setAttribute("aria-label", "Line or branch");
    var g = document.createElement("optgroup"); g.label = "Subway";
    LINES.forEach(function(l){
      var o = document.createElement("option"); o.value = l; o.textContent = l;
      if (!col.agency && l === col.line) o.selected = true; g.appendChild(o);
    });
    s.appendChild(g);
    ["L", "M"].forEach(function(ag){
      var og = document.createElement("optgroup"); og.label = RAIL[ag].name;
      RAIL[ag].branches.forEach(function(b){
        var o = document.createElement("option");
        o.value = ag + ":" + b.r; o.textContent = b.n;
        if (col.agency === ag && String(col.line) === b.r) o.selected = true;
        og.appendChild(o);
      });
      s.appendChild(og);
    });
    s.onchange = function(){
      var v = s.value;
      if (v.indexOf(":") > 0){
        var p = v.split(":");
        // Switching agency invalidates the stations -- they're from different
        // catalogs entirely -- so clear rather than carry a stale pick over.
        if (col.agency !== p[0]){ col.origin = null; col.dest = null; }
        col.agency = p[0]; col.line = p[1];
      } else {
        if (col.agency){ col.origin = null; col.dest = null; }
        col.agency = ""; col.line = v;
      }
      renderTrains(); renderStripe();
    };
    sel.innerHTML = br
      ? '<span class="rr" style="background:' + br.c + '">' + esc(br.s) + '</span>'
      : bulletHTML(col.line || "6");
    sel.appendChild(s);

    var wrap = document.createElement("div"); wrap.className = "dest ac";
    var inp = document.createElement("input"); inp.className = "inp";
    inp.placeholder = "Heading to…";
    inp.setAttribute("aria-label", "Destination");
    inp.value = (col.dest && col.dest.name) || "";
    var lst = document.createElement("div"); lst.className = "ac-list hidden";
    wrap.appendChild(inp); wrap.appendChild(lst);
    if (br){
      autocomplete(inp, lst,
        "/api/catalog/rail?agency=" + col.agency + "&route=" + col.line + "&q=",
        railRow, function(st){
          col.dest = { stop_id: st.stop_id, name: st.name, lat: st.lat, lon: st.lon };
          inp.value = st.name;
        });
    } else {
      autocomplete(inp, lst, "/api/catalog/stops?q=", stationRow, function(st){
        col.dest = { name: st.name, lat: st.lat, lon: st.lon };
        inp.value = st.name;
      });
    }

    var x = document.createElement("button");
    x.type = "button"; x.className = "x"; x.innerHTML = "&times;";
    x.title = "Remove this train"; x.setAttribute("aria-label", "Remove train");
    x.onclick = function(){ edit.columns.splice(i, 1); renderTrains(); };

    row.appendChild(sel); row.appendChild(wrap); row.appendChild(x);

    // Rail needs its own origin: a Metro-North station is rarely the subway
    // stop outside your door, and the direction of travel is worked out from
    // origin -> destination.
    if (br){
      var from = document.createElement("div"); from.className = "from";
      var lab = document.createElement("label"); lab.textContent = "From";
      var fw = document.createElement("div"); fw.className = "ac";
      var fi = document.createElement("input"); fi.className = "inp";
      fi.placeholder = "Your station on this branch…";
      fi.setAttribute("aria-label", "Origin station");
      fi.value = (col.origin && col.origin.name) || "";
      var fl = document.createElement("div"); fl.className = "ac-list hidden";
      fw.appendChild(fi); fw.appendChild(fl);
      autocomplete(fi, fl,
        "/api/catalog/rail?agency=" + col.agency + "&route=" + col.line + "&q=",
        railRow, function(st){
          // Strip the agency prefix: the resolver re-applies it, and the raw
          // stop id is what the feed carries.
          col.origin = { stop_id: st.stop_id.slice(1), name: st.name,
                         lat: st.lat, lon: st.lon };
          fi.value = st.name;
        });
      from.appendChild(lab); from.appendChild(fw);
      row.appendChild(from);
    }

    box.appendChild(row);
  });
  $("addTrain").disabled = edit.columns.length >= 4;
  renderStripe();
}

// Masthead rule, segmented into the colours of the configured lines.
function renderStripe(){
  var el = $("stripe"); if (!el) return;
  var cols = (edit && edit.columns) || [];
  if (!cols.length){ el.innerHTML = ""; return; }
  el.innerHTML = cols.map(function(c){
    var br = branchOf(c);
    if (br) return '<i style="background:' + br.c + '"></i>';
    var L = String(c.line || "").toUpperCase();
    return '<i style="background:' + (LINE_COLORS[L] || "#0C0F16") + '"></i>';
  }).join("");
}

function fillForm(){
  $("name").value = edit.name || "";
  $("alerts").value = String((edit.cadence && edit.cadence.alerts_every_min) || 5);
  setPick($("addrPick"), edit.weather
    ? (edit.weather.label || (Number(edit.weather.lat).toFixed(4) + ", " + Number(edit.weather.lon).toFixed(4)))
    : "");
  setPick($("homePick"), edit.home && edit.home.name
    ? edit.home.name + (edit.home.routes ? "  ·  " + edit.home.routes : "") : "");
  setPick($("cbPick"), edit.citibike && edit.citibike.name ? edit.citibike.name
    : (edit.citibike && edit.citibike.station_id ? "Station set" : ""));
  renderStyles();
  renderTrains();
}

function collect(){
  edit.name = $("name").value;
  edit.cadence = edit.cadence || {};
  edit.cadence.alerts_every_min = parseInt($("alerts").value, 10);
  return edit;
}

// Rendered panels, cached as object URLs so flipping between them is instant
// (and so changing a setting only re-renders the "next" state).
var shots = { now: null, next: null };
var showing = "now";

function paint(){
  var g = $("glass"), img = $("boardImg"), url = shots[showing];
  $("tabNow").classList.toggle("on", showing === "now");
  $("tabNext").classList.toggle("on", showing === "next");
  $("tabNow").setAttribute("aria-selected", String(showing === "now"));
  $("tabNext").setAttribute("aria-selected", String(showing === "next"));
  if (url){ img.src = url; img.hidden = false; g.classList.remove("empty"); }
  else { img.hidden = true; g.classList.add("empty"); }
}

function show(which){ showing = which; paint(); }

function render(which, payload){
  var g = $("glass");
  g.classList.add("busy"); g.classList.remove("empty");
  return fetch("/api/preview", { method:"POST",
      headers:{ "Content-Type":"application/json", "Authorization":"Bearer " + token },
      body: JSON.stringify(payload) })
    .then(function(r){
      if (!r.ok) return r.json().catch(function(){ return {}; })
        .then(function(j){ throw new Error(j.error || ("Preview failed (" + r.status + ")")); });
      return r.blob();
    })
    .then(function(b){
      if (shots[which]) URL.revokeObjectURL(shots[which]);
      shots[which] = URL.createObjectURL(b);
      g.classList.remove("busy");
      showing = which; paint();
    })
    .catch(function(e){
      g.classList.remove("busy"); paint();
      setMsg($("status"), e.message, "err");
    });
}

function renderBefore(){
  return fetch("/api/config?device=" + encodeURIComponent(deviceId))
    .then(function(r){ return r.json(); })
    .then(function(cfg){
      $("revNow").textContent = "rev " + cfg.config_rev;
      return render("now", { config: cfg });
    })
    .catch(function(){});
}

function doPreview(){
  setMsg($("status"), "", "");
  return render("next", { edit: collect() });
}

function save(){
  var btn = $("saveBtn"); btn.disabled = true;
  setMsg($("status"), "Saving…", "");
  fetch("/api/devices/" + encodeURIComponent(deviceId) + "/config", { method:"POST",
      headers:{ "Content-Type":"application/json", "Authorization":"Bearer " + token },
      body: JSON.stringify(collect()) })
    .then(function(r){ return r.json().then(function(j){ return { ok:r.ok, j:j }; }); })
    .then(function(res){
      btn.disabled = false;
      if (!res.ok){ setMsg($("status"), res.j.error || "Save failed", "err"); return; }
      setMsg($("status"), "Saved — your board updates within about 5 minutes.", "ok");
      renderBefore();
    })
    .catch(function(){ btn.disabled = false;
      setMsg($("status"), "Network error — nothing was saved.", "err"); });
}

// ---- wire up ----
autocomplete($("addr"), $("addrList"), "/api/geocode?q=",
  function(g){ return '<span class="nm">' + esc(g.name) + '</span>'; },
  function(g){
    edit.weather = { lat:g.lat, lon:g.lon, label:g.name,
                     tz:g.tz || (edit.weather && edit.weather.tz) || "America/New_York" };
    $("addr").value = ""; setPick($("addrPick"), g.name);
  });

autocomplete($("home"), $("homeList"), "/api/catalog/stops?q=", stationRow, function(s){
  fetch("/api/catalog/complex?id=" + encodeURIComponent(s.complex_id))
    .then(function(r){ return r.json(); })
    .then(function(d){
      var stops = {}, first = null;
      (d.results || []).forEach(function(r){
        String(r.routes || "").trim().split(/\\s+/).forEach(function(l){
          if (l){ stops[l] = r.stop_id; if (!first) first = r.stop_id; }
        });
      });
      edit.home = { complex_id:s.complex_id, name:s.name, lat:s.lat, lon:s.lon,
                    stop_id:first, stops:stops, routes:String(s.routes || "").trim() };
      $("home").value = "";
      setPick($("homePick"), s.name + (s.routes ? "  ·  " + String(s.routes).trim() : ""));
    });
});

autocomplete($("cb"), $("cbList"), "/api/catalog/citibike?q=",
  function(s){ return '<span class="nm">' + esc(s.name) + '</span>'; },
  function(s){
    edit.citibike = { station_id:s.station_id, name:s.name };
    $("cb").value = ""; setPick($("cbPick"), s.name);
  });

$("addTrain").onclick = function(){
  if (edit.columns.length < 4){ edit.columns.push({ line:"6", dest:null }); renderTrains(); } };
$("tabNow").onclick = function(){ show("now"); };
$("tabNext").onclick = function(){
  if (shots.next) show("next"); else doPreview();
};
$("loginBtn").onclick = login;
$("logoutBtn").onclick = logout;
$("previewBtn").onclick = doPreview;
$("saveBtn").onclick = save;
$("pin").addEventListener("keydown", function(e){ if (e.key === "Enter") login(); });
$("displayId").addEventListener("keydown", function(e){ if (e.key === "Enter") $("pin").focus(); });

// Boot: brief splash over the skyline, then either straight into the editor
// (session still good) or the sign-in card.
setTimeout(function(){
  $("boot").classList.add("hidden");
  if (token && deviceId){ start(); }
  else { $("signin").classList.remove("hidden"); $("displayId").focus(); }
}, 620);
</script>
</body></html>`;
