import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import base64
import requests
import os
import json
from datetime import datetime
from pathlib import Path
from typing import NamedTuple, List, Dict, Any, Optional
import sys

if sys.version_info >= (3, 9):
    from typing import Annotated
else:
    pass


# --- Type Definitions (using NamedTuple for structured data) ---
class FileMetadata(NamedTuple):
    size: int
    lastModified: str


class FileInfo(NamedTuple):
    name: str
    metadata: FileMetadata


# --- Global Variables ---
selected_file: Optional[Path] = None
SUPA_UNPACK_API_URL: Optional[str] = None
SUPA_MAIN_API_URL: Optional[str] = None

# Declare log_text_area globally but initialize it to None
# It will be assigned the actual widget later in main()
log_text_area: Optional[tk.Text] = None


# --- Helper Functions ---
def add_log(message: str) -> None:
    """Function to add a log message to the log text area."""
    # Check if log_text_area has been initialized before using it
    if log_text_area:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_text_area.insert(tk.END, f"[{current_time}] {message}\n")
        log_text_area.see(tk.END)
    else:
        # Fallback if log_text_area isn't ready (e.g., during early config loading)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")


def get_env_variable(var_name: str, error_message: str) -> Optional[str]:
    """Retrieves an environment variable and shows an error if not found."""
    value = os.getenv(var_name)
    if not value:
        add_log(error_message) # This add_log call is the problem area
        messagebox.showerror("Configuration Error", error_message)
        return None
    return value


def get_auth_token() -> Optional[str]:
    """Retrieves the authorization token from environment variables."""
    return get_env_variable("SUPA_AUTH_TOKEN", "Error: Authorization token not found in environment variables!")


# --- Core Logic Functions (unchanged, as the issue is in GUI setup order) ---
def choose_file() -> None:
    global selected_file
    default_folder = Path.home() / "Documents"

    file_path_str: str = filedialog.askopenfilename(
        initialdir=str(default_folder),
        title="Select a File",
        filetypes=(("All Files", "*.*"), ("PDF Files", "*.pdf"), ("ZIP Files", "*.zip"))
    )
    if file_path_str:
        selected_file = Path(file_path_str)
        file_label.config(text=f"Selected: {selected_file.name}")
        add_log(f"Selected file: {selected_file}")
    else:
        selected_file = None
        file_label.config(text="No file selected")
        add_log("No file selected")


def submit_file() -> None:
    if not selected_file:
        messagebox.showerror("Error", "No file selected!")
        add_log("Error: No file selected!")
        return

    if SUPA_UNPACK_API_URL is None:
        messagebox.showerror("Configuration Error", "API URL not configured. Please set SUPA_UNPACK_API_URL.")
        add_log("Error: SUPA_UNPACK_API_URL is not set.")
        return

    try:
        add_log(f"Preparing to submit file: {selected_file.name}...")

        with selected_file.open("rb") as file:
            file_content = file.read()

        encoded_file = base64.b64encode(file_content).decode('utf-8')
        filename = selected_file.name

        auth_token = get_auth_token()
        if not auth_token:
            return

        headers: Dict[str, str] = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }

        data: Dict[str, str] = {
            "input": encoded_file,
            "filename": filename
        }

        response = requests.post(SUPA_UNPACK_API_URL, headers=headers, json=data, timeout=30)

        if response.status_code == 200:
            add_log("File submitted successfully!")
            add_log(f"Response: {response.text}")
            messagebox.showinfo("Success", "File submitted successfully!")
            list_files()
        else:
            error_message = f"Failed to submit file:\nStatus Code: {response.status_code}\nResponse: {response.text}"
            add_log(error_message)
            messagebox.showerror("Error", error_message)
    except requests.exceptions.RequestException as req_e:
        error_message = f"Network or API error during submission: {req_e}"
        add_log(error_message)
        messagebox.showerror("Network Error", error_message)
    except Exception as e:
        error_message = f"An unexpected error occurred during file submission: {e}"
        add_log(error_message)
        messagebox.showerror("Error", error_message)


def list_files() -> None:
    if SUPA_UNPACK_API_URL is None:
        messagebox.showerror("Configuration Error", "API URL not configured. Please set SUPA_UNPACK_API_URL.")
        add_log("Error: SUPA_UNPACK_API_URL is not set.")
        return

    try:
        add_log("Retrieving list of files...")

        auth_token = get_auth_token()
        if not auth_token:
            return

        headers: Dict[str, str] = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }

        data: Dict[str, str] = {"cmd": "list"}

        response = requests.post(SUPA_UNPACK_API_URL, headers=headers, json=data, timeout=30)

        if response.status_code == 200:
            response_data: Dict[str, Any] = response.json()
            add_log(response_data['message'])

            for child in file_tree.get_children():
                file_tree.delete(child)

            files_to_display: List[Dict[str, Any]] = sorted(
                response_data.get('files', []),
                key=lambda f: f.get('name', '').lower()
            )

            for file_item in files_to_display:
                file_name = file_item.get('name', 'N/A')
                file_size = file_item.get('metadata', {}).get('size', 0)
                last_modified = file_item.get('metadata', {}).get('lastModified', 'N/A')
                file_tree.insert("", "end", values=(file_name, file_size, last_modified))

            add_log(f"Retrieved {response_data.get('count', 0)} files.")
        else:
            error_message = f"Failed to list files:\nStatus Code: {response.status_code}\nResponse: {response.text}"
            add_log(error_message)
            messagebox.showerror("Error", error_message)
    except requests.exceptions.RequestException as req_e:
        error_message = f"Network or API error during file listing: {req_e}"
        add_log(error_message)
        messagebox.showerror("Network Error", error_message)
    except json.JSONDecodeError:
        error_message = f"Failed to parse JSON response from API. Response: {response.text}"
        add_log(error_message)
        messagebox.showerror("API Error", "Invalid JSON response from server.")
    except Exception as e:
        error_message = f"An unexpected error occurred during file listing: {e}"
        add_log(error_message)
        messagebox.showerror("Error", error_message)


def download_file(event: tk.Event) -> None:
    selected_item = file_tree.identify('item', event.x, event.y)
    if not selected_item:
        return

    item: Dict[str, Any] = file_tree.item(selected_item)
    filename: Optional[str] = item.get('values', [None])[0]

    if not filename:
        add_log("No file selected for download.")
        return

    if SUPA_MAIN_API_URL is None:
        messagebox.showerror("Configuration Error", "API URL not configured. Please set SUPA_MAIN_API_URL.")
        add_log("Error: SUPA_MAIN_API_URL is not set.")
        return

    add_log(f"Downloading file: {filename}")

    try:
        auth_token = get_auth_token()
        if not auth_token:
            return

        headers: Dict[str, str] = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }

        data: Dict[str, str] = {"download": filename}

        response = requests.post(SUPA_MAIN_API_URL, headers=headers, json=data, timeout=60)

        if response.status_code == 200:
            file_content: bytes = response.content
            save_path_str: str = filedialog.asksaveasfilename(
                initialfile=filename,
                title="Save File",
                defaultextension=".*",
                filetypes=(("All Files", "*.*"),)
            )
            if save_path_str:
                save_path = Path(save_path_str)
                with save_path.open("wb") as file:
                    file.write(file_content)
                add_log(f"File '{filename}' downloaded and saved to {save_path}.")
                messagebox.showinfo("Success", f"File saved to {save_path}")
            else:
                add_log("Download cancelled.")
        elif response.status_code == 404:
            error_message = f"File '{filename}' not found on the server."
            add_log(error_message)
            messagebox.showerror("Error", error_message)
        else:
            error_message = f"Failed to download file:\nStatus Code: {response.status_code}\nResponse: {response.text}"
            add_log(error_message)
            messagebox.showerror("Error", error_message)
    except requests.exceptions.RequestException as req_e:
        error_message = f"Network or API error during download: {req_e}"
        add_log(error_message)
        messagebox.showerror("Network Error", error_message)
    except Exception as e:
        error_message = f"An unexpected error occurred during download: {e}"
        add_log(error_message)
        messagebox.showerror("Error", error_message)


# --- GUI Initialization ---
def main() -> None:
    """Main function to set up and run the Tkinter application."""
    global root, file_label, log_text_area, file_tree, selected_file # Add log_text_area to global list
    global SUPA_UNPACK_API_URL, SUPA_MAIN_API_URL

    root = tk.Tk()
    root.title("File Submitter")
    root.geometry("800x600")

    selected_file = None # Ensure selected_file is initialized early

    # --- Initialize log_text_area first ---
    # Create a minimalistic log area immediately to catch early errors
    log_frame_early = ttk.Frame(root)
    # Don't grid it yet, just create the widget to make it accessible
    # Use a simpler text widget for initial logging
    # log_text_area = tk.Text(log_frame_early, height=5, wrap="word", state="normal", font=('TkFixedFont', 10))
    # It's better to create the actual log_text_area where it belongs in the layout,
    # but ensure it's available via its global name before config loading.

    # TEMPORARY LOGGING DURING CONFIG SETUP:
    # A cleaner approach is to have a simple print statement for initial config errors,
    # or to defer the error logging to the Tkinter widget until it's ready.
    # For now, let's create log_text_area right away and then grid it later.

    # 1. Create the Text widget and assign it to the global log_text_area variable.
    #    It doesn't need to be gridded/packed yet for add_log to work.
    log_text_area = tk.Text(root, height=10, wrap="word", state="normal", font=('TkFixedFont', 10))
    # Note: It's defined on `root`, but then we'll re-grid/re-parent it later
    # within a `log_frame`. A better way is to move ALL widget creation to after
    # config loading, or handle early logs to console.

    # Let's adjust so only console logging happens BEFORE Tkinter setup is complete.
    # The `messagebox.showerror` will still work without `log_text_area`.

    # --- Load Configuration from Environment Variables ---
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Loading environment variables...")

    # We modify get_env_variable to initially print to console if log_text_area is not ready.
    # The messagebox will always work.
    global SUPA_UNPACK_API_URL, SUPA_MAIN_API_URL

    # Define a local helper for initial config loading that prints to console instead of log_text_area
    def _initial_get_env_variable(var_name: str, error_message: str) -> Optional[str]:
        value = os.getenv(var_name)
        if not value:
            # Use print for early errors, as log_text_area might not be fully ready
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {error_message} (via console)")
            messagebox.showerror("Configuration Error", error_message)
            return None
        return value

    SUPA_UNPACK_API_URL = _initial_get_env_variable(
        "SUPA_UNPACK_API_URL",
        "Error: SUPA_UNPACK_API_URL environment variable not set. "
        "Example: https://cc.supabase.co/functions/v1/super-worker/unpack?code=SGVsbG8K"
    )
    SUPA_MAIN_API_URL = _initial_get_env_variable(
        "SUPA_MAIN_API_URL",
        "Error: SUPA_MAIN_API_URL environment variable not set. "
        "Example: https://cc.supabase.co/functions/v1/super-worker"
    )
    auth_token_check = _initial_get_env_variable( # Also check auth token here early
        "SUPA_AUTH_TOKEN",
        "Error: Authorization token (SUPA_AUTH_TOKEN) not found in environment variables!"
    )


    # If any critical URL/token is missing, it's better to exit
    if SUPA_UNPACK_API_URL is None or SUPA_MAIN_API_URL is None or auth_token_check is None:
        messagebox.showerror("Configuration Error", "Application URLs or Token not fully configured. Exiting.")
        sys.exit(1)


    # --- GUI Widgets (moved after config loading) ---
    # Now that critical config is loaded, we can confidently set up the GUI
    # and know that add_log will work if needed later.

    file_frame = ttk.LabelFrame(root, text="File Operations", padding="10")
    file_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="ew")

    choose_button = ttk.Button(file_frame, text="Choose File", command=choose_file)
    file_label = ttk.Label(file_frame, text="No file selected", relief="sunken", anchor="w")
    submit_button = ttk.Button(file_frame, text="Submit File", command=submit_file)
    file_list_button = ttk.Button(file_frame, text="Refresh File List", command=list_files)

    choose_button.grid(row=0, column=0, padx=5, pady=5, sticky="w")
    file_label.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
    submit_button.grid(row=1, column=0, padx=5, pady=5, sticky="ew")
    file_list_button.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

    file_frame.columnconfigure(1, weight=1)

    log_label = ttk.Label(root, text="Logs:")
    log_label.grid(row=1, column=0, columnspan=2, sticky="w", padx=10)

    log_frame = ttk.Frame(root)
    log_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=5, sticky="ew")

    # Now assign the global log_text_area widget (which was implicitly created as None before)
    # The actual Text widget creation is here, after config and root window is ready
    log_text_area = tk.Text(log_frame, height=10, wrap="word", state="normal", font=('TkFixedFont', 10))
    log_text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    log_scrollbar = ttk.Scrollbar(log_frame, command=log_text_area.yview)
    log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    log_text_area['yscrollcommand'] = log_scrollbar.set

    # Log initial configuration status AFTER log_text_area is ready
    add_log("Application initialized. Configuration loaded.")
    add_log(f"SUPA_UNPACK_API_URL: {'Set' if SUPA_UNPACK_API_URL else 'Not Set (Error)'}")
    add_log(f"SUPA_MAIN_API_URL: {'Set' if SUPA_MAIN_API_URL else 'Not Set (Error)'}")
    add_log(f"SUPA_AUTH_TOKEN: {'Set' if auth_token_check else 'Not Set (Error)'}")


    file_list_label = ttk.Label(root, text="Remote File List (double-click to download):")
    file_list_label.grid(row=3, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 0))

    tree_frame = ttk.Frame(root)
    tree_frame.grid(row=4, column=0, columnspan=2, padx=10, pady=5, sticky="nsew")

    columns = ("name", "size", "last_modified")
    file_tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
    file_tree.heading("name", text="File Name")
    file_tree.heading("size", text="File Size (bytes)")
    file_tree.heading("last_modified", text="Last Modified")

    file_tree.column("name", width=250, anchor="w", stretch=tk.YES)
    file_tree.column("size", width=100, anchor="e")
    file_tree.column("last_modified", width=180, anchor="center")

    file_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    tree_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=file_tree.yview)
    tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    file_tree.configure(yscrollcommand=tree_scrollbar.set)

    file_tree.bind("<Double-1>", download_file)

    root.columnconfigure(0, weight=1)
    root.columnconfigure(1, weight=1)
    root.rowconfigure(2, weight=1)
    root.rowconfigure(4, weight=3)

    root.mainloop()


if __name__ == "__main__":
    main()
