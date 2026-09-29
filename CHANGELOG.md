# Changelog

Français : [CHANGELOG.fr.md](CHANGELOG.fr.md)

Released versions live in the
[Releases](https://github.com/Yielloow/Plume/releases). The reasoning behind
each change is in the commit messages.

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
