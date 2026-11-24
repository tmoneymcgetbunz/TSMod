# Installing TSMod on Steam Deck

Everything below happens in **Desktop Mode**. The game itself is then played in Gaming Mode as usual.

## 1. Switch to Desktop Mode
Hold the power button and pick **Switch to Desktop**.

## 2. Download the mod
Open Firefox (or another browser), download `TSMod_v1.zip` from the [Releases](../../releases) page, and open your
Downloads folder. Right-click the zip → **Extract → Extract archive here**.

## 3. Install the pak
1. In Steam (the desktop app), right-click Triangle Strategy → **Manage → Browse local files**. The file manager
   (Dolphin) opens in the game's folder.
2. Go into `TRIANGLE_STRATEGY/Content/Paks`.
3. Copy `TSMod_P.pak` from the extracted folder into `Paks`, next to `TRIANGLE_STRATEGY-WindowsNoEditor.pak`.
   Don't rename it.

## 4. Turn off Steam Cloud and back up your saves
- **Steam Cloud:** in Steam, right-click the game → **Properties → General** and turn off Steam Cloud. Otherwise
  Steam can replace a save the editor just wrote with its older cloud copy.
- **Backup:** the saves live inside the game's Proton folder, which is hidden. In Dolphin, press **Ctrl+H** to show
  hidden folders, then go to:
  - internal storage: `~/.local/share/Steam/steamapps/compatdata/1850510/pfx/drive_c/users/steamuser/Documents/My Games/TRIANGLE_STRATEGY/Steam/<id>/SaveGames`
  - SD card: the same path from `steamapps/compatdata/1850510/` in the card's Steam library.

  Copy the whole `SaveGames` folder somewhere safe.

## 5. Run the save editor (if you need it)
You need the editor to add the recruits to a save you started before installing the mod. A New Game doesn't need it.

1. Open the extracted `SaveEditor` folder in Dolphin.
2. Right-click an empty spot → **Open Terminal Here**.
3. Type the following and press Enter:
   ```
   sh "TSMod Save Editor.sh"
   ```
   File names on the Deck are case-sensitive: type the capitals exactly as shown. Easier: type `sh TS` and press
   **Tab**, and the terminal fills in the rest.

SteamOS's own Python runs the editor; there's nothing to install. It finds the game and your saves on its own
(internal storage and SD card). Close the game before writing a save; the editor checks, and backs up the whole save
folder before every write.

## 6. Play
Use the **Return to Gaming Mode** shortcut on the desktop and start the game.
- **New Game:** all 20 recruits join right after the Chapter 1 battle.
- **A save you added the recruits to with the editor:** they join at the next story scene or world-map visit.

The nine "(Cut Content)" battles are in the Story Battles list.

## Notes
- **Crash reports:** the editor's **Export crash logs…** button is untested on the Deck so far. The game's crash folder
  is next to the saves, under `.../TRIANGLE_STRATEGY/Steam/Crashes`.
- **Uninstall:** delete `TSMod_P.pak` from the `Paks` folder. A save with the recruits in it needs the pak to load,
  so keep playing saves made before installing, or your backup.
