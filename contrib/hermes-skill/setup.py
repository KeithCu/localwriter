#!/usr/bin/env python3
import urllib.request
import urllib.error
import urllib.parse
import json
import sys
import os

MCP_PORT = 8765
MCP_URL = f"http://localhost:{MCP_PORT}"
STATUS_URL = f"{MCP_URL}/status"  # WriterAgent might not have a formal /status, but we can try to connect to the MCP SSE endpoint or root.

def check_writeragent_mcp():
    """Pings the WriterAgent MCP server to see if it's active."""
    print(f"[*] Checking for WriterAgent MCP server on port {MCP_PORT}...")
    try:
        # Just opening a connection to the port to see if it's bound and responds to HTTP
        req = urllib.request.Request(MCP_URL, method="GET")
        with urllib.request.urlopen(req, timeout=3) as _:
            pass
        return True
    except urllib.error.HTTPError as e:
        # If it returns an HTTP error (like 404), there is still a server there, which is good!
        return True
    except urllib.error.URLError:
        return False
    except Exception:
        return False

def main():
    print("=== Hermes & WriterAgent Setup Helper ===\n")
    
    is_running = check_writeragent_mcp()
    
    if is_running:
        print("[+] WriterAgent MCP server detected!\n")
    else:
        print("[-] WriterAgent MCP server NOT detected.")
        print("    Please ensure LibreOffice is running, WriterAgent is installed,")
        print("    and the MCP server is enabled in WriterAgent settings.\n")
        response = input("    Continue anyway? (y/N): ").strip().lower()
        if response != 'y':
            print("Setup aborted.")
            sys.exit(1)
            
    print("How would you like to configure Hermes?")
    print("1) Create a dedicated 'office' profile (Recommended)")
    print("2) Show manual config snippet for default config.yaml")
    print("3) Cancel")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == '1':
        print("\n[*] To create the profile, we will instruct Hermes to run:")
        cmd = f"hermes profile create office --with-mcp writeragent={MCP_URL}"
        print(f"    $ {cmd}\n")
        
        # It's better to guide the user rather than blindly running subprocess since Hermes needs to be in PATH
        print("Run the command above in your terminal where Hermes Agent is installed.")
        print("Then start it using: hermes --profile office")
        
    elif choice == '2':
        print("\n[*] Add the following to your Hermes config.yaml (usually ~/.config/hermes/config.yaml):\n")
        print("mcp_servers:")
        print("  writeragent:")
        print(f"    url: '{MCP_URL}'")
        
    else:
        print("Setup aborted.")

if __name__ == "__main__":
    main()
