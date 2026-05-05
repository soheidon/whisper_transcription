using System.Diagnostics;
using System.IO;
using System.Windows;
using System.Windows.Documents;
using System.Windows.Media;

namespace WhisperGUILauncher;

public partial class MainWindow : Window
{
    private bool _hasGuiPy;
    private bool _hasCondaExe;
    private bool _hasCondaEnv;
    private bool _hasPythonw;
    private bool _hasFfmpeg;
    private LauncherSettings _settings = null!;
    private bool _isChecking;

    public MainWindow()
    {
        InitializeComponent();
        _settings = LauncherSettings.Load(LauncherConfig.LauncherSettingsPath);
    }

    private async void Window_Loaded(object sender, RoutedEventArgs e)
    {
        if (_settings.ShouldSkipCheck())
        {
            // Quick skip: trust last verification
            SetStatus($"Environment OK (verified {_settings.DaysAgoText()})", "#4ec94e");
            Log($"Environment previously verified ({_settings.DaysAgoText()}). Skipping check.", "#888");
            Log("Press 'Recheck' to run a full check.", "#888");
            _hasGuiPy = File.Exists(LauncherConfig.GuiPyPath);
            _hasCondaEnv = true; // assumed from last check
            LaunchButton.IsEnabled = _hasGuiPy;
            RecheckButton.IsEnabled = true;
        }
        else
        {
            await RunEnvironmentChecks(force: true);
        }
    }

    private async void RecheckButton_Click(object sender, RoutedEventArgs e)
    {
        await RunEnvironmentChecks(force: true);
    }

    // ---- Environment checks ----

    private async Task RunEnvironmentChecks(bool force = false)
    {
        if (_isChecking) return;
        _isChecking = true;
        RecheckButton.IsEnabled = false;
        LaunchButton.IsEnabled = false;
        SetStatus("Checking environment...", "#888");

        ClearLog();
        LogHeader("Environment Check");

        var projectDir = LauncherConfig.ResolveProjectDir();
        var guiPyPath = LauncherConfig.GuiPyPath;

        // 1. gui.py
        _hasGuiPy = File.Exists(guiPyPath);
        Log(_hasGuiPy
            ? $"  OK  gui.py found at: {guiPyPath}"
            : $"  FAIL  gui.py not found at: {guiPyPath}",
            _hasGuiPy ? "#4ec94e" : "#e74c3c");

        // 2. conda.exe
        var condaExe = LauncherConfig.FindCondaExe();
        _hasCondaExe = condaExe != null;
        Log(_hasCondaExe
            ? $"  OK  conda: {condaExe}"
            : "  FAIL  conda.exe not found (check Anaconda/Miniconda install)",
            _hasCondaExe ? "#4ec94e" : "#e74c3c");

        // 3. Conda environment
        _hasCondaEnv = false;
        if (_hasCondaExe)
        {
            var envCheck = await RunAndCapture(condaExe!, "env list");
            _hasCondaEnv = envCheck.Contains(LauncherConfig.CondaEnvName);
        }
        Log(_hasCondaEnv
            ? $"  OK  Conda env '{LauncherConfig.CondaEnvName}' exists"
            : $"  FAIL  Conda env '{LauncherConfig.CondaEnvName}' not found",
            _hasCondaEnv ? "#4ec94e" : "#e74c3c");

        // 4. pythonw.exe
        _hasPythonw = LauncherConfig.PythonwExe != null && File.Exists(LauncherConfig.PythonwExe);
        Log(_hasPythonw
            ? $"  OK  pythonw.exe: {LauncherConfig.PythonwExe}"
            : "  WARN  pythonw.exe not found (will use conda run fallback)",
            _hasPythonw ? "#4ec94e" : "#e5c07b");

        // 5. ffmpeg
        var ffmpegCheck = await RunAndCapture("where", "ffmpeg");
        _hasFfmpeg = !string.IsNullOrWhiteSpace(ffmpegCheck) && !ffmpegCheck.Contains("Could not find");
        Log(_hasFfmpeg
            ? $"  OK  ffmpeg: {ffmpegCheck.Trim()}"
            : "  WARN  ffmpeg not found in PATH (video files won't work)",
            _hasFfmpeg ? "#4ec94e" : "#e5c07b");

        // 6. CUDA
        if (_hasPythonw && _hasGuiPy)
        {
            var cudaScript = "import torch; print(f'CUDA available: {torch.cuda.is_available()}'); " +
                             "print(f'Device count: {torch.cuda.device_count()}') if torch.cuda.is_available() else None";
            var cudaResult = await RunAndCapture(LauncherConfig.PythonwExe!,
                $"-c \"{cudaScript}\"");
            var cudaStatus = cudaResult.Trim();
            Log(!string.IsNullOrWhiteSpace(cudaStatus)
                ? $"  OK  {cudaStatus.Replace("\r", "").Replace("\n", " | ")}"
                : "  WARN  Could not check CUDA status",
                cudaStatus.Contains("True") ? "#4ec94e" : "#e5c07b");
        }

        LogSeparator();

        // Update status and buttons
        var allOk = _hasGuiPy && _hasCondaEnv;
        if (allOk)
        {
            SetStatus("Environment OK — ready to launch", "#4ec94e");
        }
        else
        {
            SetStatus("Some components are missing — use Setup below", "#e5c07b");
        }

        UpdateSetupPanel();
        LaunchButton.IsEnabled = _hasGuiPy;
        RecheckButton.IsEnabled = true;

        // Save verification status
        if (allOk || force)
        {
            _settings.SetupVerified = allOk;
            _settings.SetupVerifiedAt = DateTime.UtcNow.ToString("o");
            _settings.Save(LauncherConfig.LauncherSettingsPath);
        }
        _isChecking = false;
    }

    // ---- Setup panel control ----

    private void UpdateSetupPanel()
    {
        InstallCondaEnvBtn.Visibility = Visibility.Collapsed;
        InstallPipDepsBtn.Visibility = Visibility.Collapsed;
        InstallFfmpegBtn.Visibility = Visibility.Collapsed;

        var anyVisible = false;

        // Show "Create Conda Env" only if conda.exe exists but env is missing
        if (_hasCondaExe && !_hasCondaEnv)
        {
            InstallCondaEnvBtn.Visibility = Visibility.Visible;
            anyVisible = true;
        }

        // Show "Install pip deps" if conda env exists (deps might be missing or outdated)
        if (_hasCondaEnv)
        {
            InstallPipDepsBtn.Visibility = Visibility.Visible;
            anyVisible = true;
        }

        // Show "Install ffmpeg" if missing
        if (!_hasFfmpeg)
        {
            InstallFfmpegBtn.Visibility = Visibility.Visible;
            anyVisible = true;
        }

        SetupPanel.Visibility = anyVisible ? Visibility.Visible : Visibility.Collapsed;
    }

    // ---- Install handlers ----

    private async void InstallCondaEnv_Click(object sender, RoutedEventArgs e)
    {
        InstallCondaEnvBtn.IsEnabled = false;
        LogHeader("Creating Conda Environment");
        Log($"  Creating '{LauncherConfig.CondaEnvName}' with Python 3.11...", "#e5c07b");
        SetStatus("Creating conda environment...", "#e5c07b");

        var result = await RunAndCaptureAsync(LauncherConfig.CondaExe!,
            $"create -n {LauncherConfig.CondaEnvName} python=3.11 -y",
            output => Dispatcher.Invoke(() => Log($"  {output}", "#888")));

        if (result.Contains("ERROR") || result.Contains("failed"))
        {
            Log($"  FAIL  {result}", "#e74c3c");
            SetStatus("Failed to create conda environment", "#e74c3c");
        }
        else
        {
            Log("  Done. Environment created.", "#4ec94e");
            SetStatus("Environment created — Recheck to continue", "#4ec94e");
        }

        InstallCondaEnvBtn.IsEnabled = true;
    }

    private async void InstallPipDeps_Click(object sender, RoutedEventArgs e)
    {
        InstallPipDepsBtn.IsEnabled = false;
        LogHeader("Installing Python Dependencies");

        var reqPath = LauncherConfig.RequirementsPath;
        if (!File.Exists(reqPath))
        {
            Log($"  FAIL  requirements.txt not found at: {reqPath}", "#e74c3c");
            InstallPipDepsBtn.IsEnabled = true;
            return;
        }

        Log($"  Running pip install -r requirements.txt...", "#e5c07b");
        SetStatus("Installing dependencies...", "#e5c07b");

        var result = await RunAndCaptureAsync(LauncherConfig.CondaExe!,
            $"run -n {LauncherConfig.CondaEnvName} pip install -r \"{reqPath}\"",
            output => Dispatcher.Invoke(() => Log($"  {output}", "#888")));

        if (result.Contains("ERROR") || result.Contains("failed"))
        {
            Log($"  FAIL  {result}", "#e74c3c");
            SetStatus("pip install failed — check log", "#e74c3c");
        }
        else
        {
            Log("  Done. Dependencies installed.", "#4ec94e");
            SetStatus("Dependencies installed — Recheck to verify", "#4ec94e");
        }

        InstallPipDepsBtn.IsEnabled = true;
    }

    private async void InstallFfmpeg_Click(object sender, RoutedEventArgs e)
    {
        InstallFfmpegBtn.IsEnabled = false;
        LogHeader("Installing ffmpeg");

        // Try winget first (Windows 11 built-in), fall back to choco
        var wingetCheck = await RunAndCapture("where", "winget");
        var hasWinget = !string.IsNullOrWhiteSpace(wingetCheck) && !wingetCheck.Contains("Could not find");

        string tool, args;
        if (hasWinget)
        {
            tool = "winget";
            args = "install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements";
            Log("  Using winget to install ffmpeg...", "#e5c07b");
        }
        else
        {
            var chocoCheck = await RunAndCapture("where", "choco");
            var hasChoco = !string.IsNullOrWhiteSpace(chocoCheck) && !chocoCheck.Contains("Could not find");
            if (hasChoco)
            {
                tool = "choco";
                args = "install ffmpeg -y";
                Log("  Using Chocolatey to install ffmpeg...", "#e5c07b");
            }
            else
            {
                Log("  FAIL  Neither winget nor Chocolatey found.", "#e74c3c");
                Log("  Please install ffmpeg manually: https://ffmpeg.org/download.html", "#e5c07b");
                Log("  Or install Chocolatey first: https://chocolatey.org/install", "#e5c07b");
                SetStatus("Cannot auto-install ffmpeg", "#e74c3c");
                InstallFfmpegBtn.IsEnabled = true;
                return;
            }
        }

        SetStatus("Installing ffmpeg...", "#e5c07b");

        var result = await RunAndCaptureAsync(tool, args,
            output => Dispatcher.Invoke(() => Log($"  {output}", "#888")));

        if (result.Contains("ERROR") || result.Contains("failed") || result.Contains("error"))
        {
            Log($"  FAIL  {result}", "#e74c3c");
            Log("  Try installing ffmpeg manually: https://ffmpeg.org/download.html", "#e5c07b");
            SetStatus("ffmpeg install failed — check log", "#e74c3c");
        }
        else
        {
            Log("  Done. You may need to restart the launcher for PATH to update.", "#4ec94e");
            _hasFfmpeg = true;
            UpdateSetupPanel();
            SetStatus("ffmpeg installed — restart recommended", "#4ec94e");
        }

        InstallFfmpegBtn.IsEnabled = true;
    }

    // ---- Launch logic ----

    private void LaunchButton_Click(object sender, RoutedEventArgs e)
    {
        LaunchButton.IsEnabled = false;
        LogHeader("Launching Whisper GUI");

        var projectDir = LauncherConfig.ResolveProjectDir();
        var guiPyPath = LauncherConfig.GuiPyPath;

        if (!File.Exists(guiPyPath))
        {
            Log("  ERROR  gui.py not found. Cannot launch.", "#e74c3c");
            MessageBox.Show($"gui.py not found at:\n{guiPyPath}",
                "Launch Error", MessageBoxButton.OK, MessageBoxImage.Error);
            LaunchButton.IsEnabled = true;
            return;
        }

        // Tier 1: pythonw.exe direct
        var pythonwExe = LauncherConfig.PythonwExe;
        if (pythonwExe != null && File.Exists(pythonwExe))
        {
            Log("  Starting with pythonw.exe (no console)...", "#4ec94e");
            SetStatus("Launching Whisper GUI...", "#e5c07b");
            var ok = StartProcess(pythonwExe, $"\"{guiPyPath}\"", projectDir);
            if (ok)
            {
                Log("  Launched successfully.", "#4ec94e");
                OnGuiLaunched();
                return;
            }
            Log("  WARN  pythonw.exe failed, trying conda run...", "#e5c07b");
        }

        // Tier 2: conda run pythonw
        var condaExe = LauncherConfig.CondaExe;
        if (condaExe != null)
        {
            Log("  Starting with conda run pythonw...", "#e5c07b");
            SetStatus("Launching via conda...", "#e5c07b");
            var ok = StartProcess(condaExe,
                $"run -n {LauncherConfig.CondaEnvName} pythonw \"{guiPyPath}\"", projectDir);
            if (ok)
            {
                Log("  Launched successfully via conda run.", "#4ec94e");
                OnGuiLaunched();
                return;
            }
            Log("  WARN  conda run pythonw failed, trying conda run python...", "#e5c07b");

            // Tier 3: conda run python (last resort)
            Log("  Starting with conda run python (may flash console)...", "#e5c07b");
            SetStatus("Launching via conda (fallback)...", "#e5c07b");
            ok = StartProcess(condaExe,
                $"run -n {LauncherConfig.CondaEnvName} python \"{guiPyPath}\"", projectDir);
            if (ok)
            {
                Log("  Launched successfully via conda run python.", "#4ec94e");
                OnGuiLaunched();
                return;
            }
        }

        Log("  ERROR  All launch methods failed.", "#e74c3c");
        SetStatus("Launch failed — check log", "#e74c3c");
        MessageBox.Show(
            "Could not launch gui.py.\n\n" +
            "Check the log for details. Make sure the Conda environment\n" +
            $"'{LauncherConfig.CondaEnvName}' is properly set up.",
            "Launch Error", MessageBoxButton.OK, MessageBoxImage.Error);
        LaunchButton.IsEnabled = true;
    }

    private void OnGuiLaunched()
    {
        SetStatus("Whisper GUI is running", "#4ec94e");

        if (AutoCloseCheckBox.IsChecked == true)
        {
            Log("  Auto-close enabled. Launcher will exit.", "#888");
            Task.Delay(2000).ContinueWith(_ => Dispatcher.Invoke(() => Application.Current.Shutdown()));
        }
        else
        {
            LaunchButton.Content = "Relaunch Whisper GUI";
            LaunchButton.IsEnabled = true;
        }
    }

    // ---- Process helpers ----

    private static bool StartProcess(string fileName, string arguments, string workingDir)
    {
        try
        {
            var psi = new ProcessStartInfo
            {
                FileName = fileName,
                Arguments = arguments,
                WorkingDirectory = workingDir,
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true
            };

            Process.Start(psi);
            return true;
        }
        catch (Exception ex)
        {
            Debug.WriteLine($"StartProcess failed: {ex.Message}");
            return false;
        }
    }

    private static async Task<string> RunAndCapture(string fileName, string arguments)
    {
        try
        {
            var psi = new ProcessStartInfo
            {
                FileName = fileName,
                Arguments = arguments,
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true
            };

            using var proc = Process.Start(psi);
            if (proc == null) return "";

            var output = await proc.StandardOutput.ReadToEndAsync();
            var error = await proc.StandardError.ReadToEndAsync();
            await proc.WaitForExitAsync();

            return string.IsNullOrWhiteSpace(output) ? error : output;
        }
        catch
        {
            return "";
        }
    }

    private static async Task<string> RunAndCaptureAsync(string fileName, string arguments,
        Action<string>? onOutputLine)
    {
        try
        {
            var psi = new ProcessStartInfo
            {
                FileName = fileName,
                Arguments = arguments,
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true
            };

            using var proc = Process.Start(psi);
            if (proc == null) return "";

            var result = "";
            while (!proc.StandardOutput.EndOfStream)
            {
                var line = await proc.StandardOutput.ReadLineAsync();
                if (line != null)
                {
                    result += line + "\n";
                    onOutputLine?.Invoke(line);
                }
            }
            while (!proc.StandardError.EndOfStream)
            {
                var line = await proc.StandardError.ReadLineAsync();
                if (line != null)
                {
                    result += line + "\n";
                    onOutputLine?.Invoke(line);
                }
            }

            await proc.WaitForExitAsync();
            return result;
        }
        catch
        {
            return "";
        }
    }

    // ---- Logging helpers ----

    private void ClearLog()
    {
        Dispatcher.Invoke(() => LogBox.Document.Blocks.Clear());
    }

    private void LogHeader(string text)
    {
        Log($"=== {text} ===", "#888");
    }

    private void LogSeparator()
    {
        Log("", "");
    }

    private void Log(string message, string colorHex)
    {
        Dispatcher.Invoke(() =>
        {
            var p = new Paragraph();
            p.Inlines.Add(new Run(message)
            {
                Foreground = ParseColor(colorHex)
            });
            LogBox.Document.Blocks.Add(p);
            LogBox.ScrollToEnd();
        });
    }

    private void SetStatus(string text, string colorHex)
    {
        Dispatcher.Invoke(() =>
        {
            StatusLabel.Text = text;
            StatusIcon.Foreground = ParseColor(colorHex);
        });
    }

    private static SolidColorBrush ParseColor(string hex)
    {
        try
        {
            return (SolidColorBrush)new BrushConverter().ConvertFrom(hex)!;
        }
        catch
        {
            return Brushes.Gray;
        }
    }

    // ---- Window events ----

    private void CloseButton_Click(object sender, RoutedEventArgs e)
    {
        Application.Current.Shutdown();
    }
}
