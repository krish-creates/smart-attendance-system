# 🎓 AI Smart Attendance System

An end-to-end, AI-powered attendance management system built with Python, Flask, OpenCV, and `face_recognition`. This system allows teachers to register students by capturing their biometric face data via webcam, start attendance sessions, automatically recognize faces in real-time, and generate attendance reports.

---

## 🛠️ Tech Stack
*   **Backend**: Python 3.10, Flask, SQLite3
*   **Frontend**: HTML5, Bootstrap 5, JavaScript
*   **Computer Vision**: OpenCV (`opencv-python`), `face_recognition`, `dlib`

---

## 🚀 Step-by-Step Setup Guide (For VS Code)

Follow these instructions carefully to set up and run the project on a new machine. Because we are dealing with computer vision libraries (`dlib` and `face_recognition`), **using Conda is highly recommended** to avoid C++ build errors.

### Step 1: Prerequisites
Before you begin, ensure you have the following installed on your system:
1.  **[Visual Studio Code](https://code.visualstudio.com/)**: The code editor.
2.  **[Miniconda](https://docs.conda.io/en/latest/miniconda.html)** or **Anaconda**: Essential for easily installing the `dlib` library without needing complex C++ build tools.

### Step 2: Open the Project
1.  Open **VS Code**.
2.  Go to `File` > `Open Folder...` and select the `smart-attendance` folder.
3.  Open a new terminal in VS Code (`Terminal` > `New Terminal`).
4.  Ensure your terminal is using **Command Prompt** or **PowerShell**.

### Step 3: Create the Virtual Environment
We will create an isolated environment specifically for this project to prevent version conflicts.
Run the following commands in the VS Code terminal:

```bash
# Create a new conda environment named 'attendance' with Python 3.10
conda create -n attendance python=3.10 -y

# Activate the environment
conda activate attendance
```
*(You should now see `(attendance)` at the beginning of your terminal prompt).*

### Step 4: Install Dependencies (CRITICAL STEP)
The `face_recognition` library relies on `dlib`. Installing `dlib` via `pip` usually fails on Windows unless you have Visual Studio C++ Build Tools configured perfectly. 
**To bypass this, we use conda-forge to install dlib first:**

```bash
# 1. Install dlib via conda-forge (This takes a moment, be patient)
conda install -c conda-forge dlib -y

# 2. Install the rest of the dependencies via pip
pip install -r requirements.txt
```

### Step 5: Run the Application
Once all dependencies are installed, you can start the server:

```bash
python app.py
```

You should see output similar to:
`* Running on http://127.0.0.1:5000/ (Press CTRL+C to quit)`

### Step 6: Access the Website
1.  Open your web browser (Chrome or Edge recommended).
2.  Navigate to: `http://127.0.0.1:5000`
3.  You will see the Dashboard!

---

## 💡 How to Use the System

1.  **Register a Student**: Click `Register New Student`. Enter their details (Name, Reg No, Dept). The webcam will open. Look at the camera and wait until it captures **20 frames**. The system will save their face biometric data.
2.  **Start a Session**: Click `Start Attendance Session`. Enter the Class and Subject names.
3.  **Take Attendance**: In the Active Sessions table, click the green `Open` button. The webcam will turn on. As registered students walk in front of the camera, their names will appear, and their attendance will be instantly recorded in the database.
4.  **End Session**: When class is over, click `End Session` to stop taking attendance.
5.  **View Reports**: Go to the `Report` page to view, filter, and review who was present for every past session.
6.  **Manage Data**: You can reset all sessions using the `Reset Total Sessions` button on the dashboard, or completely delete a student and their photos using the secure `Delete` button.

---

## ⚠️ Troubleshooting & Alternatives

If you run into issues during setup, here are the most common problems and their solutions:

### 1. `dlib` Fails to Install
**Error**: You get red error text when trying to install dependencies.
**Solution**: 
*   Ensure you are using **Conda** to install dlib: `conda install -c conda-forge dlib`.
*   *Alternative*: If you absolutely cannot use Conda and must use standard Python (`pip`), you must install [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) and select the **"Desktop development with C++"** workload before running `pip install dlib`.

### 2. "Starting the CLR failed" or "MemoryError: bad allocation"
**Error**: The server crashes instantly when running `python app.py`.
**Solution**: This happens occasionally in Conda environments when loading heavy AI models. Simply run the command `python app.py` again. It usually resolves itself on the second try.

### 3. Port 5000 is Already in Use
**Error**: `Address already in use` or the website fails to load.
**Solution**: Another program is using port 5000. You can change the port by modifying the bottom of `app.py`:
Change `app.run(debug=True)` to `app.run(debug=True, port=5001)`. Then access the site at `http://127.0.0.1:5001`.

### 4. Webcam Not Turning On
**Error**: The screen stays black on the Capture or Recognition pages.
**Solution**: 
*   Ensure your browser has **permission** to access the camera (check the lock icon in the URL bar).
*   Ensure no other application (like Zoom or Teams) is currently using the camera.

### 5. `ModuleNotFoundError: No module named 'flask'`
**Error**: Python can't find the libraries.
**Solution**: You forgot to activate your environment. Run `conda activate attendance` and try again.
