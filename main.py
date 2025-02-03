import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import subprocess
import threading
from queue import Queue
import time

class QuestAppInstaller:
    def __init__(self, root):
        self.root = root
        self.root.title("---ToQuest!---")
        self.root.geometry("600x600")
        
        self.apk_path = ""
        self.log_queue = Queue()
        self.device_model = ""
        self.connected = False
        self.checking_device = False
        
        self.create_widgets()
        self.update_logs()
        self.check_adb_connection()

    def create_widgets(self):
        # Check Device Button
        check_btn = ttk.Button(self.root, text="Check Device", command=self.start_device_check)
        check_btn.pack(pady=5)

        # APK File Selection
        file_frame = ttk.Frame(self.root)
        file_frame.pack(pady=10, padx=10, fill=tk.X)
        
        self.file_entry = ttk.Entry(file_frame, width=50)
        self.file_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)
        
        browse_btn = ttk.Button(file_frame, text="Browse APK", command=self.browse_apk)
        browse_btn.pack(side=tk.LEFT, padx=5)

        # Install Button
        install_btn = ttk.Button(self.root, text="Install APK", command=self.start_installation)
        install_btn.pack(pady=5)

        # Logs
        log_frame = ttk.Frame(self.root)
        log_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        
        self.log_text = tk.Text(log_frame, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)

    def start_device_check(self):
        if self.checking_device:
            return
            
        self.checking_device = True
        self.log_queue.put("Starting 20-second device check...\n")
        
        thread = threading.Thread(target=self.device_check_process, daemon=True)
        thread.start()

    def device_check_process(self):
        start_time = time.time()
        device_found = False
        
        while time.time() - start_time < 20 and not device_found:
            try:
                result = subprocess.run(
                    ["adb", "devices", "-l"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                devices = [line for line in result.stdout.split('\n') if 'device' in line and 'offline' not in line]
                if len(devices) > 1:
                    device_info = devices[0].split()
                    device_id = device_info[0]
                    device_model = next((s.split(':')[1] for s in device_info if 'model:' in s), 'Unknown')
                    
                    self.root.after(0, lambda: messagebox.showinfo(
                        "Device Found",
                        f"Success!\nModel: {device_model}\nADB ID: {device_id}"
                    ))
                    device_found = True
                    self.log_queue.put(f"Device found: {device_model} ({device_id})\n")
                    
            except Exception as e:
                self.log_queue.put(f"Check error: {str(e)}\n")
            
            time.sleep(1)
        
        if not device_found:
            self.root.after(0, lambda: messagebox.showwarning(
                "Timeout",
                "No devices found within 20 seconds!"
            ))
            self.log_queue.put("Device check timeout\n")
        
        self.checking_device = False

    def check_adb_connection(self):
        def check_device():
            try:
                result = subprocess.run(
                    ["adb", "devices"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if "device" in result.stdout:
                    self.get_device_model()
                    self.connected = True
                    self.root.title(f"---ToQuest! [{self.device_model}]---")
                else:
                    self.request_adb_connection()
            except Exception as e:
                self.log_queue.put(f"ADB Error: {str(e)}\n")

        threading.Thread(target=check_device, daemon=True).start()

    def request_adb_connection(self):
        ip_address = simpledialog.askstring(
            "ADB Connection",
            "Enter device IP address:",
            parent=self.root
        )
        if ip_address:
            self.log_queue.put(f"Trying to connect to {ip_address}...\n")
            try:
                subprocess.run(
                    ["adb", "connect", f"{ip_address}:5555"],
                    check=True,
                    timeout=10
                )
                self.check_adb_connection()
            except subprocess.CalledProcessError:
                messagebox.showerror("Connection Failed", "Failed to connect to device")
                self.connected = False
            except Exception as e:
                messagebox.showerror("Error", f"Connection error: {str(e)}")
                self.connected = False

    def get_device_model(self):
        try:
            result = subprocess.run(
                ["adb", "shell", "getprop", "ro.product.model"],
                capture_output=True,
                text=True,
                timeout=5
            )
            self.device_model = result.stdout.strip()
        except Exception as e:
            self.device_model = "Unknown Device"
            self.log_queue.put(f"Error getting model: {str(e)}\n")

    def browse_apk(self):
        file_path = filedialog.askopenfilename(filetypes=[("APK files", "*.apk")])
        if file_path:
            self.apk_path = file_path
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, file_path)

    def start_installation(self):
        if not self.connected:
            messagebox.showwarning("Not Connected", "Please connect to device first!")
            self.check_adb_connection()
            return
            
        if not self.apk_path:
            messagebox.showerror("Error", "Please select an APK file first!")
            return
            
        thread = threading.Thread(target=self.install_apk, daemon=True)
        thread.start()

    def install_apk(self):
        self.log_queue.put("Starting installation...\n")
        
        try:
            process = subprocess.Popen(
                ["adb", "install", "-r", self.apk_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    self.log_queue.put(output)
            
            stderr = process.stderr.read()
            if stderr:
                self.log_queue.put(f"Error: {stderr}\n")
            
            return_code = process.poll()
            if return_code == 0:
                self.log_queue.put("Installation successful!\n")
            else:
                messagebox.showerror("Error!", f"Error code: {return_code}")
        
        except Exception as e:
            self.log_queue.put(f"Error: {str(e)}\n")

    def update_logs(self):
        while not self.log_queue.empty():
            message = self.log_queue.get()
            self.log_text.insert(tk.END, message)
            self.log_text.see(tk.END)
        self.root.after(100, self.update_logs)

if __name__ == "__main__":
    root = tk.Tk()
    try:
        root.iconbitmap("./files/favicon.ico")
    except Exception as e:
        print(f"Error loading icon: {e}")
    app = QuestAppInstaller(root)
    root.mainloop()