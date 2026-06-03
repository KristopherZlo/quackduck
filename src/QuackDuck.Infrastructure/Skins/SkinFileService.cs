using System.Collections.ObjectModel;
using System.IO;
using System.IO.Compression;
using System.Text.Json;
using QuackDuck.Application.Abstractions;
using QuackDuck.Domain.Skins;

namespace QuackDuck.Infrastructure.Skins;

public sealed class SkinFileService : ISkinService
{
    private readonly IAppPathProvider _paths;
    private readonly SkinDefinition _defaultSkin;

    public SkinFileService(IAppPathProvider paths)
    {
        _paths = paths;
        _defaultSkin = LoadDefaultSkin();
    }

    public SkinDefinition DefaultSkin => _defaultSkin;

    public async Task<SkinDefinition> LoadSkinAsync(string? skinPath, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(skinPath))
        {
            return _defaultSkin;
        }

        if (Directory.Exists(skinPath))
        {
            var loaded = BuildSkinFromFolder(
                Path.GetFileName(skinPath),
                Path.Combine(skinPath, "config.json"),
                skinPath,
                isDefault: false,
                sourcePath: skinPath);
            if (loaded != null)
            {
                return loaded;
            }
        }

        if (File.Exists(skinPath) && Path.GetExtension(skinPath).Equals(".zip", StringComparison.OrdinalIgnoreCase))
        {
            var loaded = await LoadZipSkinAsync(skinPath, cancellationToken);
            if (loaded != null)
            {
                return loaded;
            }
        }

        return _defaultSkin;
    }

    public async Task<IReadOnlyList<SkinDefinition>> DiscoverAsync(string? rootFolder, CancellationToken cancellationToken = default)
    {
        var skins = new List<SkinDefinition> { _defaultSkin };

        if (!string.IsNullOrWhiteSpace(rootFolder) && Directory.Exists(rootFolder))
        {
            var rootConfig = Path.Combine(rootFolder, "config.json");
            var rootSkin = BuildSkinFromFolder(Path.GetFileName(rootFolder), rootConfig, rootFolder, isDefault: false, sourcePath: rootFolder);
            if (rootSkin != null)
            {
                skins.Add(rootSkin);
            }

            foreach (var skinFolder in Directory.EnumerateDirectories(rootFolder, "*", SearchOption.TopDirectoryOnly))
            {
                cancellationToken.ThrowIfCancellationRequested();
                var configPath = Path.Combine(skinFolder, "config.json");
                var skin = BuildSkinFromFolder(Path.GetFileName(skinFolder), configPath, skinFolder, isDefault: false, sourcePath: skinFolder);
                if (skin != null)
                {
                    skins.Add(skin);
                }
            }

            foreach (var zipPath in Directory.EnumerateFiles(rootFolder, "*.zip", SearchOption.TopDirectoryOnly))
            {
                cancellationToken.ThrowIfCancellationRequested();
                var skin = await LoadZipSkinAsync(zipPath, cancellationToken);
                if (skin != null)
                {
                    skins.Add(skin);
                }
            }
        }

        return new ReadOnlyCollection<SkinDefinition>(skins);
    }

    private SkinDefinition LoadDefaultSkin()
    {
        var defaultFolder = Path.Combine(_paths.AssetsRoot, "skins", "default");
        var configPath = Path.Combine(defaultFolder, "config.json");
        return BuildSkinFromFolder("default", configPath, defaultFolder, isDefault: true, sourcePath: defaultFolder)
               ?? new SkinDefinition(
                   id: "default",
                   spriteSheetPath: Path.Combine(defaultFolder, "spritesheet.png"),
                   frameWidth: 32,
                   frameHeight: 32,
                   animations: new Dictionary<string, AnimationSequence>(),
                   soundFiles: new[] { Path.Combine(defaultFolder, "wuak.wav") },
                   isDefault: true,
                   sourcePath: defaultFolder);
    }

    private async Task<SkinDefinition?> LoadZipSkinAsync(string skinPath, CancellationToken cancellationToken)
    {
        var tempExtract = Path.Combine(_paths.TempRoot, $"skin_{Guid.NewGuid():N}");
        Directory.CreateDirectory(tempExtract);

        await using var stream = File.OpenRead(skinPath);
        using var archive = new ZipArchive(stream, ZipArchiveMode.Read);
        archive.ExtractToDirectory(tempExtract, overwriteFiles: true);

        var configPath = Path.Combine(tempExtract, "config.json");
        var skin = BuildSkinFromFolder(Path.GetFileNameWithoutExtension(skinPath), configPath, tempExtract, isDefault: false, sourcePath: skinPath);

        if (skin == null)
        {
            TryDelete(tempExtract);
        }

        return skin;
    }

    private SkinDefinition? BuildSkinFromFolder(string id, string configPath, string folder, bool isDefault, string? sourcePath)
    {
        if (!File.Exists(configPath))
        {
            return null;
        }

        try
        {
            using var doc = JsonDocument.Parse(File.ReadAllText(configPath));
            var root = doc.RootElement;

            if (!root.TryGetProperty("frame_width", out var fwProp) ||
                !root.TryGetProperty("frame_height", out var fhProp) ||
                !root.TryGetProperty("animations", out var animProp))
            {
                return null;
            }

            var frameWidth = fwProp.GetInt32();
            var frameHeight = fhProp.GetInt32();
            var animations = ParseAnimations(animProp);

            var spriteSheetName = root.TryGetProperty("spritesheet", out var sheetProp)
                ? sheetProp.GetString()
                : null;
            if (string.IsNullOrWhiteSpace(spriteSheetName))
            {
                return null;
            }

            var spriteSheetPath = Path.Combine(folder, spriteSheetName);
            var soundFiles = ParseSoundFiles(root, folder);

            return new SkinDefinition(
                id: id,
                spriteSheetPath: spriteSheetPath,
                frameWidth: frameWidth,
                frameHeight: frameHeight,
                animations: animations,
                soundFiles: soundFiles,
                isDefault: isDefault,
                sourcePath: sourcePath);
        }
        catch
        {
            return null;
        }
    }

    private static Dictionary<string, AnimationSequence> ParseAnimations(JsonElement animationsRoot)
    {
        var animations = new Dictionary<string, AnimationSequence>(StringComparer.OrdinalIgnoreCase);
        foreach (var anim in animationsRoot.EnumerateObject())
        {
            var frames = new List<FrameCoordinate>();
            if (anim.Value.ValueKind == JsonValueKind.Array)
            {
                foreach (var frameEl in anim.Value.EnumerateArray())
                {
                    var frameString = frameEl.GetString();
                    if (string.IsNullOrWhiteSpace(frameString))
                    {
                        continue;
                    }

                    var parts = frameString.Split(new[] { ':', ',', ';' }, StringSplitOptions.RemoveEmptyEntries);
                    if (parts.Length == 2 &&
                        int.TryParse(parts[0], out var row) &&
                        int.TryParse(parts[1], out var col))
                    {
                        frames.Add(new FrameCoordinate(row, col));
                    }
                }
            }

            animations[anim.Name] = new AnimationSequence(anim.Name, frames);
        }

        return animations;
    }

    private static IReadOnlyList<string> ParseSoundFiles(JsonElement root, string folder)
    {
        var soundPaths = new List<string>();
        if (root.TryGetProperty("sound", out var soundProp))
        {
            if (soundProp.ValueKind == JsonValueKind.String)
            {
                var name = soundProp.GetString();
                if (!string.IsNullOrWhiteSpace(name))
                {
                    soundPaths.Add(Path.Combine(folder, name));
                }
            }
            else if (soundProp.ValueKind == JsonValueKind.Array)
            {
                foreach (var item in soundProp.EnumerateArray())
                {
                    var name = item.GetString();
                    if (!string.IsNullOrWhiteSpace(name))
                    {
                        soundPaths.Add(Path.Combine(folder, name));
                    }
                }
            }
        }

        return soundPaths;
    }

    private static void TryDelete(string folder)
    {
        try
        {
            if (Directory.Exists(folder))
            {
                Directory.Delete(folder, recursive: true);
            }
        }
        catch
        {
            // best-effort cleanup
        }
    }
}
