# Changelog

Français : [CHANGELOG.fr.md](CHANGELOG.fr.md)

Released versions live in the
[Releases](https://github.com/Yielloow/Plume/releases). The reasoning behind
each change is in the commit messages.

## 1.0.25 (2026-10-09)

- **Tab sleeping is gone.** The engine's browser process died three times in
  six days, always on a video page, and Windows never said a word about it: no
  error report, no graphics driver reset, no memory exhaustion. Sleeping was
  the only thing Plume asked of the engine that touches its process-level
  memory management, `TrySuspendAsync` and `MemoryUsageTargetLevel` set to
  Low. It is the best-placed suspect, and the only one that can be removed
  without losing anything essential. Plume now holds more memory: a browser
  that weighs is better than a browser that closes. The module, the delay and
  the dot marking a sleeping tab go with it.
- **Automatic recovery is off by default.** Spotting a freeze is one thing,
  closing someone's browser is another, and a false alarm costs more than the
  freeze. Plume notes what it sees in profil/plantages.txt and stops there;
  "Restart Plume" waits in the gear panel. The `reprise_auto` setting in
  config.json turns it back on for those who want it.
- **Plume takes the pulse of the page you are looking at, and gets itself out
  of a freeze.** Until now a page that stopped answering stayed that way:
  neither F5 nor an address reached it, and the only cure was quitting Plume
  and starting it again. It now asks the engine a trivial question every four
  seconds, and what counts is that an answer comes back. What is measured is
  how long a question has gone unanswered, never the time since the last word:
  a tab left aside is never asked anything, and taking it for a frozen one
  would reload healthy pages. After twenty-five seconds with no answer, Plume
  asks the other tabs for their pulse and gives them time to reply: if one
  answers, the engine is fine and that one renderer is stuck, so its view is
  rebuilt; if none answers, the engine itself is gone, and Plume saves the
  session and restarts, which is what you had to do by hand.
- **"Restart Plume" in the gear panel.** It is the only command still
  answering when every page is frozen, because Plume draws it, not the engine.
  Your tabs come back.
- **Windows a page asks for really open now.** Plume opened a tab at the
  right address and stopped there, while a page calling window.open expects a
  window object, the one it then writes into. Sites that open "about:blank"
  and fill it afterwards, including the ads some sites make you watch before a
  stream, only ever got a blank tab, blank for good. The window is now handed
  back to the page.
- **An ad is also recognised by its parameters.** The address reported carried
  lp_key, clickid, trk, feed and zone on a throwaway domain no list will ever
  know. Pairs of parameters now give it away, compared by exact name so that a
  "timezone" is not taken for a sold zone, along with a surer mark still: a
  domain that starts with the very click id it carries.
- **A refused advertising window says so, and leaves you the last word.** Some
  sites demand you watch their ads before showing what you came for, and a
  silent refusal left you in front of a page going nowhere with no reason
  given. A banner now says it and offers to open it anyway, and that tab is no
  longer filtered.
- **The what's new page no longer reports itself.** It quotes the changelog,
  which describes the "click allow to prove you are not a robot" scam. The
  detector found both a plea and a pretext there, and put its warning screen
  over one of Plume's own pages. A notification scam arrives over the web and
  never from a local file: the warning now only applies to http and https
  pages.
- **A tab left alone no longer comes back mute.** A background tab is
  suspended after ninety seconds. Coming back to it during that suspension
  found nothing to wake, because the tab is only marked asleep once the
  suspension completes: the suspension then landed on a page being looked at.
  Nothing answered any more, and typing an address changed nothing either, a
  suspended engine ignoring the navigations sent to it. A suspension now
  cancels itself if you come back, waking a tab is only recorded once it has
  really worked, every way of navigating wakes the tab first, and a
  tab you are looking at that the engine reports as suspended is brought
  back: when the window returns to the front, when it is resized, and
  otherwise every fifteen seconds. A tab brought back also picks up the
  current size again: while suspended it had not followed the changes, which
  is why the page was painted three quarters of the way into the corner of
  the window, and why enlarging the window did not fix it.
- **After an engine crash, Plume no longer vanishes entirely.** The new Plume
  waits for the old one, but when the old one outlives that wait, the new one
  used to hand it the address and leave, and the old one closed right after.
  The incident log showed exactly that case. A Plume relaunched after a crash
  now opens its own window and hands nothing over: two windows are better
  than no browser.
- **Pages that set no background of their own are readable again.** Plume
  paints a dark background under pages so that a new tab does not flash white,
  but that is also the background a page without one receives: LinkedIn leaves
  html and body transparent with near-black text, and came out black on black.
  The dark now covers only the wait. As soon as a page announces itself the
  background turns white, unless the page declares itself dark, in which case
  it keeps the dark a browser would give it.
- **A page that stops answering can be brought back.** When a renderer
  freezes, neither F5 nor a click reaches it, since both are addressed to it:
  that is the tab left all black with nothing clickable. Plume now replaces
  the view itself, which means a new process. Ctrl+Shift+R does it on demand,
  and Plume does it on its own when a page reports itself empty a second time,
  or when the engine says a renderer has stopped answering. Three attempts at
  most, so a page that is empty by nature does not loop.

## 1.0.24 (2026-09-30)

- **Plume no longer closes itself after an engine crash.** The restart added
  in this version launched the new Plume while the old one was still alive:
  the new one found the local channel busy, assumed another Plume was
  running, handed over its address and left, and the old one closed right
  after. The new Plume now waits for the old to be gone, and the old only
  closes once the new one has really started. Engine incidents are written to
  profil/plantages.txt, readable without turning anything on.
- **The streaming pop-up trick is blocked.** Those sites load their own script
  that listens to every click on the page and opens an ad on the same gesture
  as the link you actually wanted. A window opened while you were clicking a
  link must now lead where that link led, or stay on the site; anything else
  is refused. Buttons are untouched, so sign-in pop-ups still work.
- **Ads are now recognised by their shape, not just their name.** Streaming ad
  networks change domain every day, but their addresses always carry the same
  marks: afu.php, clickid, extclickid, zoneid, cost, tsid. Those addresses are
  refused, whether they come as a request, as a window the page asks for, or
  as a redirection. Third-party frames in standard banner sizes are hidden too.
- **A page that begs you to press Allow now gets a full warning screen**, with
  a button to close the tab. The fake "I'm not a robot" checkbox is a lure:
  what it really wants is permission to push ads to your desktop. Plume
  refuses the permission and says so.
- **Notification requests are refused.** A page asking to send you
  notifications almost never has a good reason, and it is the whole point of
  the "click Allow to prove you are not a robot" scam. Camera, microphone and
  location still ask, since there the question is real.
- A page that sends itself to a known ad network, in its own tab, is stopped.
  Only windows opened alongside were blocked before.
- The gear panel now opens the history and the downloads directly, each with
  its own icon, instead of leaving them to Ctrl+H and Ctrl+J.
- The settings panes carry titles: interface and search, history, passwords
  and forms, updates. Cards no longer stack without a word.
- Clicking a suggestion really opens it now. The list was trying to activate
  itself, so Windows ate the click and the address bar took the focus back.
- **The ad module now covers more than YouTube.** Known ad networks are
  refused before the request leaves, pop-unders are blocked (a click on a
  page only opens a window if it came from a link or a button, or stays on
  the same site), links pointing straight at an ad network go nowhere, and
  known ad slots are hidden. Still one switch, still off in one click.
- The settings are panes now, not one long page: the column on the left picks
  the one you see, the address remembers it, and a search box finds a setting
  across all of them.
- Selecting part of the address with the mouse no longer snaps back to
  selecting all of it on release.
- Clicking a suggestion in the address bar list now opens it. Only Enter
  worked before.
- A history page: search it, forget a single page, or clear everything. It
  can be switched off entirely, and a private window still writes nothing.
  Ctrl+H opens it.
- Ctrl+J reopens the downloads window, which used to appear once and never
  come back.
- YouTube's theatre mode is remembered from one video to the next.
- The theatre button in Plume's player aims better: Twitch and YouTube each
  have their own button and their own shortcut.
- Plume notices when the engine dies under it. A renderer that crashes now
  reloads its tab; if the whole browser process is gone, Plume saves the
  session and restarts into it. This is what showed as every page going
  blank at once, on every site.
- When Windows updates the WebView2 runtime while Plume is running, Plume
  says so and offers to restart, instead of waiting for the pages to die.

## 1.0.23 (2026-09-30)

- Plume no longer overwrites `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS` and
  `WEBVIEW2_USER_DATA_FOLDER`: switches and a profile path set before launch
  are kept, which is what portable setups need.

## 1.0.22 (2026-09-29)

- A "What's new" panel in the settings, fed by this changelog, and a banner
  the first time a new version starts.
- Saved passwords can be listed and forgotten one at a time. Plume never
  reads or shows the password itself, only the site, the username and the
  date.
- Password saving and form filling, on by default: the engine asks before it
  keeps anything, and everything can be erased at once.
- A way to report a problem, and to copy the details a report needs.
- A YouTube page that loads blank now reloads itself.

## 1.0.21 (2026-09-28)

- Plume's own pages refresh again: the settings page stayed in the old
  language, and the home page and settings kept the old palette after a
  colour change.
- Leaving a video's fullscreen keeps the window on the screen it was playing
  on, instead of jumping to the primary one.

## 1.0.20 (2026-09-28)

- A video page left alone for a long time recovers on its own: the player is
  examined on return, and the page reloaded if it no longer answers.
- Page audio now comes from WebView2's own process, a direct child of Plume,
  so that application sharing picks it up.
- The version shows in the corner of the home page and leads to the settings.

## 1.0.19 (2026-09-27)

- The mpv player follows the chosen colour, at launch and while playing.
- The colour reaches the timeline, the volume slider and hovered buttons.

## 1.0.18 (2026-09-27)

- A full settings page, in a tab: general, appearance, modules, about.
  Ctrl+comma opens it.
- The whole palette follows from a single colour: five themes, or your own.
  The bars, the drawn opening, the window icon and Plume's own pages follow.
- Three switchable modules: YouTube without ads, Plume's Twitch player,
  sleeping tabs.
- The active tab's background slides from one tab to the next.

## 1.0.17 (2026-09-27)

- The active tab takes the colour of the address bar and reaches down into
  it: the two bars read as one surface. Plume's spark marks the tab you are
  looking at.

## 1.0.16 (2026-09-25)

- The opening logotype is centred on its spark.
- Closing the last window plays the opening in reverse.

## 1.0.15 (2026-09-25)

- A link opened from another application brings Plume to the front.
- Middle-click and Ctrl+click open the tab in the background.
- Sleeping never puts a tab to sleep while it is playing audio.
- Tab sliding is smoother.

## 1.0.14 (2026-09-22)

- On Twitch, the site's own player is now the default; Plume's, ad-free but
  heavier on the graphics card, stays one click away.
- Notifications appear and leave smoothly.
- New site.

## 1.0.13 (2026-09-22)

- A page's fullscreen really covers the screen, Windows edges included.

## 1.0.12 (2026-09-21)

- Startup fix: 1.0.11 would not launch on some machines.
- A "Check for updates" button in the settings.

## 1.0.11 (2026-09-21)

- YouTube keeps its own player, and its ads are removed from the page.
- mpv is reserved for Twitch lives, whose ad breaks it skips.
- Full review of the interface and the settings.

## 1.0.10 (2026-09-20)

- The player no longer lands on the neighbouring tab when switching quickly.

## 1.0.9 (2026-09-14)

- The pale band at the top of the window, fixed at its source.

## 1.0.8 (2026-09-14)

- The white edge line, and the player spilling out of its area.

## 1.0.7 (2026-09-13)

- Work groups carry their colours.

## 1.0.6 (2026-09-13)

- One-click updates, with a countdown you can cancel.

## 1.0.5 (2026-09-13)

- Windows itself says which browser opens links.

## 1.0.4 (2026-09-13)

- Default browser state read from the right place in the registry.

## 1.0.3 (2026-09-13)

- Update notices arrive after the page, not before.
- Settings survive an update.

## 1.0.2 (2026-09-13)

- Volume is remembered from one video to the next.
- Taskbar icon, documentation.

## 1.0.1 (2026-09-13)

- Two languages, French and English.
- Plume can become the default browser.

## 1.0.0 (2026-09-13)

- First release: tabs, bookmarks, work groups, sleeping tabs, an embedded
  video player, a local home page.
