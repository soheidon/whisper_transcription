using System.IO;
using System.Text.Json;

namespace WhisperGUILauncher;

static class LauncherConfig
{
    public const string CondaEnvName = "whisper-transcription";
    public const string GuiScript = "gui.py";
    public const string RequirementsTxt = "requirements.txt";
    public const string LauncherSettingsFile = "launcher_settings.json";
    public const int DefaultSkipDays = 7;

    private static string? _condaExe;
    private static string? _anacondaDir;
    private static string? _projectDir;

    // ---- Conda detection ----

    public static string? FindCondaExe()
    {
        if (_condaExe != null) return _condaExe;

        var envConda = Environment.GetEnvironmentVariable("CONDA_EXE");
        if (!string.IsNullOrEmpty(envConda) && File.Exists(envConda))
        {
            _condaExe = envConda;
            _anacondaDir = Directory.GetParent(Directory.GetParent(Path.GetDirectoryName(_condaExe)!)!.FullName)!.FullName;
            return _condaExe;
        }

        var home = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        var programData = Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData);
        var candidates = new[]
        {
            Path.Combine(home, "anaconda3"),
            Path.Combine(home, "miniconda3"),
            Path.Combine(home, "miniforge3"),
            Path.Combine(home, "AppData", "Local", "anaconda3"),
            Path.Combine(programData, "anaconda3"),
            Path.Combine(programData, "miniconda3"),
        };

        foreach (var dir in candidates)
        {
            var exe = Path.Combine(dir, "Scripts", "conda.exe");
            if (File.Exists(exe))
            {
                _condaExe = exe;
                _anacondaDir = dir;
                return _condaExe;
            }
        }

        return null;
    }

    public static string? AnacondaDir => _anacondaDir ??= FindCondaExe() is not null ? _anacondaDir : null;
    public static string? CondaExe => _condaExe ??= FindCondaExe();
    public static string? PythonwExe => AnacondaDir != null
        ? Path.Combine(AnacondaDir, "envs", CondaEnvName, "pythonw.exe") : null;
    public static string? PythonExe => AnacondaDir != null
        ? Path.Combine(AnacondaDir, "envs", CondaEnvName, "python.exe") : null;

    // ---- Project directory ----

    public static string ResolveProjectDir()
    {
        if (_projectDir != null) return _projectDir;

        var exeDir = AppContext.BaseDirectory;
        var dir = exeDir;
        for (int i = 0; i < 8; i++)
        {
            if (File.Exists(Path.Combine(dir, GuiScript)))
            {
                _projectDir = dir;
                return _projectDir;
            }
            var parent = Directory.GetParent(dir);
            if (parent == null) break;
            dir = parent.FullName;
        }

        _projectDir = exeDir;
        return _projectDir;
    }

    public static string GuiPyPath => Path.Combine(ResolveProjectDir(), GuiScript);
    public static string RequirementsPath => Path.Combine(ResolveProjectDir(), RequirementsTxt);
    public static string LauncherSettingsPath => Path.Combine(ResolveProjectDir(), LauncherSettingsFile);
}

// ---- Launcher settings model ----

class LauncherSettings
{
    public bool SetupVerified { get; set; }
    public string? SetupVerifiedAt { get; set; }
    public int SetupSkipDays { get; set; } = 7;

    public static LauncherSettings Load(string path)
    {
        try
        {
            if (File.Exists(path))
            {
                var json = File.ReadAllText(path);
                return JsonSerializer.Deserialize<LauncherSettings>(json) ?? new LauncherSettings();
            }
        }
        catch { }
        return new LauncherSettings();
    }

    public void Save(string path)
    {
        try
        {
            var json = JsonSerializer.Serialize(this, new JsonSerializerOptions { WriteIndented = true });
            File.WriteAllText(path, json);
        }
        catch { }
    }

    public bool ShouldSkipCheck()
    {
        if (!SetupVerified || string.IsNullOrEmpty(SetupVerifiedAt))
            return false;

        if (DateTime.TryParse(SetupVerifiedAt, null, System.Globalization.DateTimeStyles.RoundtripKind, out var verified))
        {
            return (DateTime.UtcNow - verified.ToUniversalTime()).TotalDays < SetupSkipDays;
        }
        return false;
    }

    public string DaysAgoText()
    {
        if (!SetupVerified || string.IsNullOrEmpty(SetupVerifiedAt))
            return "never";

        if (DateTime.TryParse(SetupVerifiedAt, null, System.Globalization.DateTimeStyles.RoundtripKind, out var verified))
        {
            var days = (DateTime.UtcNow - verified.ToUniversalTime()).TotalDays;
            if (days < 1) return "today";
            if (days < 2) return "1 day ago";
            return $"{(int)days} days ago";
        }
        return "unknown";
    }
}
