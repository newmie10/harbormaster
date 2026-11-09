# Harbor Master on Linux (via touchHLE)

Play the original **Harbor Master** (Imangi Studios, 2009, iOS v2.1) on a PC,
running the real iPhone binary in [touchHLE](https://touchhle.org/), a
high-level emulator for early iOS apps. Out of the box, touchHLE can't run this
game. This repo contains the fixes that get it from "crashes on launch" to
fully playable.

Tested on Fedora 43 (GCC 15, Mesa/Intel), Hyprland/Wayland.

## Quick start

1. Install Rust (<https://rustup.rs>), `cmake`, a C/C++ compiler, `git`, `curl`.
2. Build the patched touchHLE:
   ```sh
   ./setup.sh
   ```
3. Download the game from <https://archive.org/download/harbor-master-ios>
   and save it in this folder as `HarborMaster Decrypted.ipa`.
4. Play:
   ```sh
   ./play.sh                 # 960x640 window
   ./play.sh --fullscreen    # fill the screen
   ```
   The mouse acts as your finger. Saves are stored in `touchHLE/touchHLE_sandbox/`.

Run `play.sh` from a normal terminal. touchHLE treats SIGINT/SIGTERM as "quit",
so anything that kills the process on a timeout ends your game (it saves cleanly
first).

## What's in here

| Path | Purpose |
| --- | --- |
| `setup.sh` | Fetches touchHLE at the pinned commit `ca1de89`, plus Boost headers, applies the patch, builds |
| `patches/touchhle-harbormaster.patch` | All touchHLE changes (15 files) |
| `play.sh` | Launches the game with the right options |
| `tools/uncgbi.py` | Converts the app's Apple "CgBI" PNGs into normal PNGs, to look at the art (not needed to play) |
| `assets/` | The game's images (converted to normal PNGs), sounds, sprite atlas and map files, for reference (not needed to play) |

## What it took: issues and fixes

Each step below fixed whatever stopped the game next. They're listed in the
order I ran into them.

### Building touchHLE on a modern distro

touchHLE has no Linux release, so it's built from source.

| Problem | Fix |
| --- | --- |
| dynarmic needs Boost; installing `boost-devel` needs root | `setup.sh` downloads the Boost 1.81 headers into `vendor/boost`, which touchHLE's build picks up automatically |
| GCC 15 defaults to C23, where `bool`/`false` are keywords, which breaks bundled SDL2 | Build with `CFLAGS=-std=gnu17` |
| GCC 15 no longer pulls in `<cstdint>` transitively, which breaks bundled OpenAL Soft | Build with `CXXFLAGS="-include cstdint"` |
| Linking fails: `unable to find library -lsndio`. touchHLE always links sndio on Linux, even when OpenAL didn't build that backend | Patch: removed the hardcoded `sndio` link line |

### Getting past launch: missing APIs

The game crashed on functions touchHLE hadn't implemented. One at a time:

| Crash | Fix |
| --- | --- |
| `CFURLCopyPath` unimplemented | Implemented |
| `CFURLCreateStringByReplacingPercentEscapes` unimplemented | Implemented percent-decoding, including the "characters to leave escaped" set and NULL-on-invalid-UTF-8 |
| `-[NSFileManager contentsOfDirectoryAtPath:error:]` hit a `todo!()` when the save directory doesn't exist yet (first run) | Returns a proper `NSError` (`NSFileReadNoSuchFileError`) |
| `SCNetworkReachabilityUnscheduleFromRunLoop` unimplemented (the game checks whether imangistudios.com is reachable) | Added Schedule/Unschedule. Like the existing callback stub, they report failure, so the game assumes it's offline |
| `-[UIImageView setAnimationRepeatCount:]` missing (menu play-button animation) | Added as a no-op stub, like the neighboring animation setters |
| `-[UIScrollView flashScrollIndicators]` missing | No-op (touchHLE doesn't draw scroll indicators) |

### Map select: UITableView didn't exist

The map list (`LevelListViewController`) is a `UITableViewController`. touchHLE
had **no `UITableView` at all**, and `NSIndexPath` was an empty stub. I wrote a
compact implementation:

- **`NSIndexPath`**: index storage, `indexPathForRow:inSection:`, `row`,
  `section`, `compare:`, `isEqual:`, `hash`.
- **`UITableView`** (built on `UIScrollView`):
  - sections and rows from the data source; per-row heights; section and table
    headers/footers; a background view that stays fixed while scrolling
  - selection APIs; `scrollToRowAtIndexPath:`; `willDisplayCell:`
  - tap-to-select: a touch that didn't drag selects its row, with
    `willSelect`/`didSelect`/`didDeselect` delegate calls
  - limitation: no cell reuse; `dequeueReusableCellWithIdentifier:` returns nil,
    which apps must handle anyway
- **`UITableViewCell`**: content view, text/detail labels, image view,
  background and selected-background views, selection styles, and iOS 2.x
  initializers.
- **`UITableViewController`**: its view is the table; it's the table's
  delegate and data source.

First result: the list was a **blank white box**. The cells painted themselves
white. Before iOS 7, cells take on the table's background, and the game sets
that to clear, so cells are now transparent by default.

### Invisible buttons and a black play field: the layout pass

These two bugs had the same cause. **touchHLE called `layoutSubviews` exactly
once, at launch**, so any view created later was never laid out:

- Every `UIButton`'s image view stayed 0×0. START, BACK, Achievements,
  Leaderboards and Multiplayer were all invisible. `UIButton` also never
  positioned its foreground image at all; that was a `TODO` in touchHLE.
- The game view is Apple's classic `EAGLView`, which **creates its OpenGL
  framebuffer in `layoutSubviews`**. That never ran, so the game presented
  renderbuffer 0 every frame and touchHLE dropped all of them. The result was a
  black play field, even though the game logic was running (shifts and cargo
  were being recorded).

Fix: an actual UIKit-style deferred layout pass:
- `setNeedsLayout` / `layoutIfNeeded` on `UIView`
- views are marked when added to a hierarchy (along with their superview) or
  when their bounds size changes; moving the origin, as scrolling does, doesn't
  count
- the run loop performs pending layouts each iteration
- `UIButton` now centers its image at its natural size (shrunk to fit)
- `UIView` now sends `didMoveToSuperview`

### Crashes during play

| Crash | Cause | Fix |
| --- | --- | --- |
| Pressing START: `Could not open OpenAL device` | touchHLE was built without an audio backend (no ALSA/PulseAudio headers), so the game's music failed to open a device | `play.sh` sets `ALSOFT_DRIVERS=null`, OpenAL Soft's silent output |
| Pausing: `NSThread does not respond to cancel` | Not implemented | `cancel` and `isCancelled` with a real flag (Apple semantics: the thread checks the flag and exits itself) |
| Resuming: `isCancelled` sent to a `UIView` | touchHLE didn't keep a running `NSThread` alive. The game released it after `cancel` (legal on iOS), it was freed, and the memory was reused | A started thread now retains its `NSThread` until it exits, like Apple's |

## Known issues

- **No sound.** To get it: install `alsa-lib-devel pulseaudio-libs-devel` (or
  your distro's equivalents), delete `touchHLE/target`, re-run `./setup.sh`, and
  remove the `ALSOFT_DRIVERS=null` line from `play.sh`.
- "SKILL LEVEL" overlaps its stars on the map card. touchHLE substitutes its own
  font, which is wider than the original.
- Fullscreen is letterboxed (3:2 game on a 16:10 screen).
- Frames are presented through touchHLE's slower copy path rather than its fast
  path. It plays fine, but uses more CPU.
- Not tested: Achievements, Leaderboards, Multiplayer. They use Game Center,
  which touchHLE doesn't implement, so they'll likely crash.
- Table rows have no separators or accessory icons (the game doesn't use them).

## Legal

Harbor Master is © Imangi Studios. `assets/` contains the game's art, sounds and
map data, extracted for reference. This repo contains no game code; you provide
the `.ipa` yourself.
touchHLE is MPL-2.0, and the patch is a derivative of it.
