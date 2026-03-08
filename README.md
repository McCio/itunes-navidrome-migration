# itunes-navidrome-migration
Python scripts to transfer iTunes history to a Navidrome installation

## Introduction
These Python scripts will transfer song ratings, play counts, play dates and playlists from an existing iTunes library to a Navidrome installation.

## Background
iTunes saves its data in a Library.xml file. Navidrome saves its data in up to three different `navidrome.db*` files. The script reads from `Library.xml` and writes the data to the navidrome.db file.

These scripts were tested on Linux via [uv](https://docs.astral.sh/uv/) using a Library.xml file that came from iTunes on Windows. I'm running the Docker version of Navidrome v0.60.3 & uv version 0.10.6.

I am not sure how it would work on other platforms.

## Known issues
1. Foreign alphabets and characters (e.g. Japanese) may not transfer. See [this issue](https://github.com/Stampede/itunes-navidrome-migration/issues/4) for details.

## Installation
1. I suggest installing [uv](https://docs.astral.sh/uv/).
2. Download `itunesPlaylistMigrator.py`, `itunestoND.py`.
3. `$ chmod +x itunesPlaylistMigrator.py itunestoND.py`
4. The scripts are ready to execute like `$ ./itunestoND.py`

If you do not want to use uv, check one of the two scripts for the dependencies to install.

## How to use
### Preparing your library
Set up your Navidrome server and copy all the folders and music files from your iTunes library to the Navidrome library. Navidrome will build its own database from scratch based on the file metadata. 

The most important thing is that you keep the same directory structure between iTunes and Navidrome libraries. Do not rename, delete or move any files or directories. The script uses the file paths to sync the databases. If you want to reorganize the file structure, do it after you have moved over all your iTunes data.

That said, before running the scripts, I found it very helpful to use Music Brainz Picard to clean up file metadata **without moving any files**. Use Navidrome for a week or so and if you have problems finding albums or songs, use Picard or Beets or something to improve the metadata tags for the files that are acting funny.

**Only work on backups until you know the scripts were successful.**

### Migrating play counts, last played date and song ratings
1. Shut down your Navidrome server.
2. Copy the Navidrome database files to the machine with these scripts. In my case there are 3 database files: `navidrome.db`, `navidrome.db-shm` and `navidrome.db-wal` you need any `navidrome.db*` file that you find.
3. Run the first script: `$ ./itunestoND.py`
4. It will prompt you to type the path to the `navidrome.db` and `Library.xml`
   - *in alternative, you can run directly the script with the two paths as arguments, first navidrome and the iTunes* 
5. If you already setup multiple users in navidrome, it will prompt you to choose which user to apply the migration to.
6. Wait. For large libraries, it can take a few minutes to crunch all the data in `Library.xml`.
7. After loading and matching all data, you will see a summary and be asked for confirmation to apply the migration to `navidrome.db`.
8. When it's done, your Navidrome database files may be collapsed into a single `navidrome.db` file. This is OK.
9. **On the machine with the ND server:** delete the 3 database files, then copy over the `navidrome.db` file from the script. Put it in their place.
10. Start your Navidrome server to make sure everything worked correctly. You should now have song ratings and play counts.

The script will also generate a file called `IT_file_correlations.py`. If you don't want to move over your iTunes playlists, you can just delete this.

### Migrating iTunes playlists
I wrote this as an afterthought, so these instructions are a little weird. This script will not move smart playlists. Because of the way `Library.xml` is structured, there are sometimes "false positives" when looking for playlists. You will be prompted before each playlist is created. If you don't recognize a list, just decline when it asks if you want to transfer it.

1. Backup your Navidrome database like you did for the last script in case something goes wrong.
2. Make sure your Navidrome server is running.
3. The previous script generated a file: `IT_file_correlations.py`. Move that file into the same directory where you have `itunesPlaylistMigrator.py` stored.
4. Run the playlist migrator script: `$ python3 itunesPlaylistMigrator.py`. If your working directory is not the same where `Library.xml` is stored, you will be prompted for the path to `Library.xml`.
5. Answer the prompts for your Navidrome username and password.
6. The script will search for playlists from your iTunes library and prompt if you want to move them to Navidrome.

## Acknowledgments
Thanks to [Stampede](https://github.com/Stampede) for the first version of the script.

Thanks to all the Navidrome developers for their hard work.

Hopefully these scripts help some people. Feel free to copy / share / improve etc.. As far as I'm concerned, this is public domain.

Hello.
