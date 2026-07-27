# linux-resmon
A python equivalent of the Windows Resource Monitor (resmon.exe) for Linux

Hello, world!

<b>First things first?</b>
I am NOT A PROGRAMMER. I simply had fun prompting Gemini to output all the python codes you will find in this repository.

<b>OK, now about the concept?</b>
I looked extensively for this, but I could not find a like-for-like equivalent of the Microsoft Windows Resource Monitor (resmon.exe) for Linux. All options I found are almost exclusively similar to the Task Manager or Process Monitor, but those did not interest me as I needed something graphical that could tell me disk usage (inc. rates) plus network usage (inc. outgoing IPs, etc.) and, for that purpose, not having to use too many separate TUIs like atop, etc. Also a thread that inspired me do this is an old reddit post that can be found here: https://www.reddit.com/r/linux/comments/knzzq/is_there_a_linux_equivalent_of_windows_7s/.

<b>OK, so what did I do?</b>
I thought, what about asking Gemini to code this for me for fun? This is where it came up with the ".py" files you see. All the 17 versions here uploaded represent the concept evolution, for you to have a look and audit, use and fork, and do as you well please (I think I put it under GPL3).

<b>OK, now tell me about the files?</b>
I tested all versions except Version 4 because I did not want to install the extra dependencies to draw the graphs; all other versions need python3 plus python3-pyqt6 and python3-psutil. All versions were tested on Fedora 44 KDE; I did not test this on any non-systemd systems; I did not test this on any Arch/Debian-derivative either.

<strong>The best version for me, is Version 16</strong>:
- Version 1 (tested, OK) - the OG, simple Disk and Network monitor in separate tabs. Generated in Gemini Flash.
- Version 2 (tested, OK) - I asked Gemini to give me sorting ability per column but it did not seem to work. Generated in Gemini Flash.
- Version 3 (tested, OK) - I asked it to log the history of the records so it includes a .db file. Generated in Gemini Flash.
- Version 4 (UNTESTED) - I asked Gemini to include realtime graphs; I have NOT TESTED this because it required additional dependencies and I did not want to clog my system and wanted the tool to be simple. Generated in Gemini Flash.
- Version 5 (tested, OK) - History feature removed, Disk and Network are now split-panel on the same tab. Generated in Gemini Flash.
- Version 6 (tested, OK) - CPU and Memory features added. Generated in Gemini Flash.
- Version 7 (tested, OK) - Two tabs created, one for Disk + Network, and another for CPU + Memory. Generated in Gemini Flash.
- Version 8 (tested, OK) - Tabs and panel position is now adjustable. Generated in Gemini Flash.
- Version 9 (tested, OK) - Overview tab (CPU + Memory + Disk + Network) created, along with separate tabs for each feature. Generated in Gemini Flash.
- Version 10 (tested, OK) - Now in dark mode. Generated in Gemini Flash.
- Version 11 (tested, OK) - Asked Gemini Flash for a debug. Generated in Gemini Flash.
- Version 12 (tested, OK) - Asked for Gemini Pro for a debug. Generated in Gemini Pro.
- Version 13 (tested, OK) - Followed Gemini suggestion for Delta Updates. Generated in Gemini Pro.
- Version 14 (tested, OK) - It now remmebers panel positioni (persistance). Generated in Gemini Pro.
- Version 15 (tested, OK) - It now remembers position of both panels and tabs (persistance). Generated in Gemini Pro.
- <b>VERSION 16 (TESTED, OK)</b> - THIS IS THE BEST VERSION. It now includes a light/dark switch. Generated in Gemini Pro.
- Version 17 (tested, ?fail) - Asked for Gemini Pro for a debug and I think it broke it.

<b>OK, SO HOW DO I RUN THIS?</b>
1. Ensure you have the required dependencies: python3, python3-pyqt6 and python3-psutil (attention: Version 4 needs more!).
2. Just download the python file you want.
3. On the terminal, type "sudo python3" + the name of the file you downloaded.

<hr>
I thought this was a fun little project so I decided to share in case you find it fun/useful too. I am also new in GitHub so please be kind to me :-P
