using System;
using System.IO;
using System.Diagnostics;
using System.Net;
using System.ComponentModel;
using System.Threading;

class Program
{
    static void Main(string[] args)
    {
        Console.Title = "Auto J*b Applier";
        Console.WriteLine("==============================================");
        Console.WriteLine("                Auto J*b Applier              ");
        Console.WriteLine("==============================================");
        Console.WriteLine();

        // Enable TLS 1.2 to avoid SSL handshake issues when downloading from python.org
        try
        {
            ServicePointManager.SecurityProtocol = (SecurityProtocolType)3072; // TLS 1.2
        }
        catch (Exception ex)
        {
            Console.WriteLine("Warning: Failed to set TLS 1.2 security protocol: " + ex.Message);
        }

        string pythonPath = FindPython();

        if (string.IsNullOrEmpty(pythonPath))
        {
            Console.WriteLine("Python was not found on your system.");
            Console.WriteLine("Starting automated Python installation...");
            Console.WriteLine();

            string installerPath = DownloadPythonInstaller();
            if (string.IsNullOrEmpty(installerPath))
            {
                Console.WriteLine("Error: Failed to download the Python installer.");
                Console.WriteLine("Please install Python manually from: https://www.python.org/downloads/");
                Console.WriteLine("Press any key to exit...");
                Console.ReadKey();
                return;
            }

            Console.WriteLine("Installing Python. Please wait for the installer to complete...");
            bool installed = RunPythonInstaller(installerPath);
            
            try
            {
                if (File.Exists(installerPath))
                {
                    File.Delete(installerPath);
                }
            }
            catch {}

            if (!installed)
            {
                Console.WriteLine("Error: Python installation failed or was cancelled.");
                Console.WriteLine("Please install Python manually from: https://www.python.org/downloads/");
                Console.WriteLine("Press any key to exit...");
                Console.ReadKey();
                return;
            }

            // Search for Python again after install
            pythonPath = FindPython();
            if (string.IsNullOrEmpty(pythonPath))
            {
                Console.WriteLine("Python was installed, but cannot be located in PATH yet.");
                Console.WriteLine("Searching default installation paths...");
                pythonPath = SearchDefaultPaths();
            }

            if (string.IsNullOrEmpty(pythonPath))
            {
                Console.WriteLine("Error: Python installation completed, but python.exe could not be found.");
                Console.WriteLine("Please add Python to your PATH environment variable manually.");
                Console.WriteLine("Press any key to exit...");
                Console.ReadKey();
                return;
            }

            Console.WriteLine("Python installed successfully!");
            Console.WriteLine();
        }
        else
        {
            Console.WriteLine("Python detected: " + pythonPath);
            Console.WriteLine();
        }

        RunApp(pythonPath, args);
    }

    static string FindPython()
    {
        if (CheckPythonCommand("python"))
        {
            return "python";
        }
        if (CheckPythonCommand("py"))
        {
            return "py";
        }
        return SearchDefaultPaths();
    }

    static bool CheckPythonCommand(string cmd)
    {
        try
        {
            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = cmd;
            psi.Arguments = "--version";
            psi.UseShellExecute = false;
            psi.RedirectStandardOutput = true;
            psi.RedirectStandardError = true;
            psi.CreateNoWindow = true;

            using (Process p = Process.Start(psi))
            {
                p.WaitForExit(2000);
                return p.ExitCode == 0;
            }
        }
        catch
        {
            return false;
        }
    }

    static string SearchDefaultPaths()
    {
        // 1. Check local app data
        string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        string programsPath = Path.Combine(localAppData, "Programs", "Python");
        if (Directory.Exists(programsPath))
        {
            foreach (string dir in Directory.GetDirectories(programsPath, "Python*"))
            {
                string pyExe = Path.Combine(dir, "python.exe");
                if (File.Exists(pyExe))
                {
                    return pyExe;
                }
            }
        }

        // 2. Check program files
        string programFiles = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles);
        string pfPython = Path.Combine(programFiles, "Python");
        if (Directory.Exists(pfPython))
        {
            string pyExe = Path.Combine(pfPython, "python.exe");
            if (File.Exists(pyExe)) return pyExe;
        }
        if (Directory.Exists(programFiles))
        {
            foreach (string dir in Directory.GetDirectories(programFiles, "Python*"))
            {
                string pyExe = Path.Combine(dir, "python.exe");
                if (File.Exists(pyExe))
                {
                    return pyExe;
                }
            }
        }

        // 3. Check program files (x86)
        string programFilesX86 = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86);
        if (Directory.Exists(programFilesX86))
        {
            foreach (string dir in Directory.GetDirectories(programFilesX86, "Python*"))
            {
                string pyExe = Path.Combine(dir, "python.exe");
                if (File.Exists(pyExe))
                {
                    return pyExe;
                }
            }
        }

        return null;
    }

    static string DownloadPythonInstaller()
    {
        string url = "https://www.python.org/ftp/python/3.12.4/python-3.12.4-amd64.exe";
        string tempPath = Path.Combine(Path.GetTempPath(), "python-3.12.4-amd64.exe");

        Console.WriteLine("Downloading Python 3.12.4 installer...");
        Console.WriteLine("From: " + url);

        try
        {
            using (WebClient client = new WebClient())
            {
                client.DownloadProgressChanged += (sender, e) =>
                {
                    Console.Write(string.Format("\rDownloading: {0}% ({1}MB / {2}MB)", 
                        e.ProgressPercentage, 
                        e.BytesReceived / 1024 / 1024, 
                        e.TotalBytesToReceive / 1024 / 1024));
                };

                object syncObj = new object();
                bool completed = false;

                client.DownloadFileCompleted += (sender, e) =>
                {
                    lock (syncObj)
                    {
                        completed = true;
                        Monitor.Pulse(syncObj);
                    }
                };

                lock (syncObj)
                {
                    client.DownloadFileAsync(new Uri(url), tempPath);
                    while (!completed)
                    {
                        Monitor.Wait(syncObj);
                    }
                }
                Console.WriteLine();
                Console.WriteLine("Download complete.");
                return tempPath;
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine();
            Console.WriteLine("Download error: " + ex.Message);
            return null;
        }
    }

    static bool RunPythonInstaller(string installerPath)
    {
        try
        {
            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = installerPath;
            psi.Arguments = "/passive InstallAllUsers=0 PrependPath=1 Include_test=0";
            psi.UseShellExecute = true;

            using (Process p = Process.Start(psi))
            {
                p.WaitForExit();
                return p.ExitCode == 0 || p.ExitCode == 3010;
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine("Error starting installer: " + ex.Message);
            return false;
        }
    }

    static void RunApp(string pythonPath, string[] args)
    {
        string scriptPath = "run.py";
        if (!File.Exists(scriptPath))
        {
            string exeDir = AppDomain.CurrentDomain.BaseDirectory;
            scriptPath = Path.Combine(exeDir, "run.py");
            if (!File.Exists(scriptPath))
            {
                Console.WriteLine("Error: Could not find 'run.py'. Make sure this executable is in the project root directory.");
                Console.WriteLine("Press any key to exit...");
                Console.ReadKey();
                return;
            }
        }

        Console.WriteLine("Launching: " + pythonPath + " " + scriptPath);
        Console.WriteLine("----------------------------------------------");
        Console.WriteLine();

        try
        {
            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = pythonPath;

            string argumentString = "\"" + scriptPath + "\"";
            if (args.Length > 0)
            {
                argumentString += " " + string.Join(" ", args);
            }

            psi.Arguments = argumentString;
            psi.UseShellExecute = false;
            psi.WorkingDirectory = Path.GetDirectoryName(Path.GetFullPath(scriptPath));

            using (Process p = Process.Start(psi))
            {
                p.WaitForExit();
                Environment.Exit(p.ExitCode);
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine("Error starting application: " + ex.Message);
            Console.WriteLine("Press any key to exit...");
            Console.ReadKey();
        }
    }
}
