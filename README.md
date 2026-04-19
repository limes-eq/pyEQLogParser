# pyEQLogParser
Browser-based python rewrite of EQLogParser for emu servers

All credit for the logic to the original EQLogParser: https://github.com/kauffman12/EQLogParser

I wanted to fix direct damage breakouts for emu servers, ran into the SyncFusion depdendency in the main branch, and decided to convert into a fresh take on the idea instead

The web UI allows specifying a spells_us.txt to use for DD parsing, you can also replace the default copy in pyEQLogParser/_internal/resources to avoid having to specify a path every run

<img width="1694" height="555" alt="Screenshot 2026-04-19 022336" src="https://github.com/user-attachments/assets/97de3dd8-136c-479b-a06b-1dc98ad5b4ee" />

<img width="1695" height="644" alt="Screenshot 2026-04-19 022423" src="https://github.com/user-attachments/assets/68c6ce08-2ead-4c6d-b954-5509442af4a2" />


# How to Run

## Download the packaged release and run (Windows)
No additional config needed, replace pyEQLogParser/_internal/resources/spells_us.txt with a copy from your server

## Run via Python (platform independent, requirements.txt included)
`python launch.py` and then launch http://localhost:5000 in a browser

## Create standalone package
`build.bat`

### Note: be sure to close from the system tray icon to shut down the web server
