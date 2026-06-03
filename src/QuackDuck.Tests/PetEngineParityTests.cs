using QuackDuck.Application.Rendering;
using QuackDuck.Domain.Pets;

namespace QuackDuck.Tests;

public sealed class PetEngineParityTests
{
    [Fact]
    public async Task IdleTimeout_TransitionsToSleepApproachBeforeSleeping()
    {
        var fixture = await TestPetEngineFactory.CreateStartedAsync(PetSettings.Default with
        {
            IdleDurationSeconds = 999,
            SleepTimeoutSeconds = 5,
            DirectionChangeIntervalSeconds = 999,
            RandomBehaviorEnabled = false
        });

        fixture.Engine.ForceState(PetStateKind.Idle);
        fixture.Engine.Tick(TimeSpan.FromSeconds(5.1));

        Assert.Equal(PetStateKind.SleepApproach, fixture.Engine.CurrentState.Kind);
    }

    [Fact]
    public async Task GroundOffsetDecrease_LeavesPetFallingInsteadOfFloating()
    {
        var settings = PetSettings.Default with
        {
            GroundLevelOffset = 100,
            RandomBehaviorEnabled = false
        };
        var fixture = await TestPetEngineFactory.CreateStartedAsync(settings);
        var engine = fixture.Engine;
        engine.ForceState(PetStateKind.Walking);
        engine.SetPose(100, engine.GroundLevel - engine.ScaledHeight);

        await engine.ApplySettingsAsync(settings with { GroundLevelOffset = 0 });

        Assert.Equal(PetStateKind.Falling, engine.CurrentState.Kind);
    }

    [Fact]
    public async Task Jumping_UsesPythonInitialVelocityScale()
    {
        var fixture = await TestPetEngineFactory.CreateStartedAsync(PetSettings.Default with
        {
            RandomBehaviorEnabled = false
        });
        var engine = fixture.Engine;
        engine.SetPose(100, engine.GroundLevel - engine.ScaledHeight);

        engine.ForceState(PetStateKind.Jumping);
        var beforeY = engine.Pose.Y;
        engine.Tick(TimeSpan.FromMilliseconds(20));

        Assert.InRange(beforeY - engine.Pose.Y, 21.0, 22.5);
    }

    [Fact]
    public async Task EnergyDepletion_TransitionsDirectlyToSleeping()
    {
        var fixture = await TestPetEngineFactory.CreateStartedAsync(PetSettings.Default with
        {
            RandomBehaviorEnabled = false
        });

        fixture.Engine.ForceState(PetStateKind.Walking);
        fixture.Engine.SpendEnergy(1000);

        Assert.Equal(PetStateKind.Sleeping, fixture.Engine.CurrentState.Kind);
    }

    [Fact]
    public async Task MissingAnimations_FallBackToIdleFrames()
    {
        var fixture = await TestPetEngineFactory.CreateStartedAsync(
            PetSettings.Default with { RandomBehaviorEnabled = false },
            TestPetEngineFactory.CreateSkin(includeMotionAnimations: false));
        PetFrameUpdate? lastFrame = null;
        fixture.Engine.FrameUpdated += frame => lastFrame = frame;

        fixture.Engine.ForceState(PetStateKind.Jumping);

        Assert.NotNull(lastFrame);
        Assert.Equal("idle", lastFrame.Value.Animation);
    }

    [Fact]
    public async Task AnimationFrames_AdvanceAtSlowerPythonLikeCadence()
    {
        var fixture = await TestPetEngineFactory.CreateStartedAsync(PetSettings.Default with
        {
            IdleDurationSeconds = 999,
            RandomBehaviorEnabled = false
        });
        PetFrameUpdate? lastFrame = null;
        fixture.Engine.FrameUpdated += frame => lastFrame = frame;

        fixture.Engine.ForceState(PetStateKind.Idle);
        fixture.Engine.Tick(TimeSpan.FromMilliseconds(100));
        Assert.Equal(0, lastFrame?.FrameIndex);

        fixture.Engine.Tick(TimeSpan.FromMilliseconds(50));
        Assert.Equal(1, lastFrame?.FrameIndex);
    }

    [Fact]
    public async Task DisplayScale_MultipliesPetSizeWithoutChangingUserPetSizeSetting()
    {
        var fixture = await TestPetEngineFactory.CreateStartedAsync(PetSettings.Default with
        {
            PetSize = 3,
            RandomBehaviorEnabled = false
        });

        fixture.Engine.SetDisplayScale(2.0);

        Assert.Equal(3, fixture.Engine.Settings.PetSize);
        Assert.Equal(fixture.Engine.CurrentSkin.FrameWidth * 6, fixture.Engine.ScaledWidth);
        Assert.Equal(fixture.Engine.CurrentSkin.FrameHeight * 6, fixture.Engine.ScaledHeight);
    }

    [Fact]
    public async Task PlayTestSoundAsync_PlaysCurrentSkinSoundImmediately()
    {
        var soundPath = Path.Combine(Path.GetTempPath(), $"quackduck-test-{Guid.NewGuid():N}.wav");
        File.WriteAllBytes(soundPath, Array.Empty<byte>());

        var fixture = await TestPetEngineFactory.CreateStartedAsync(PetSettings.Default with
        {
            SoundEnabled = true,
            SoundVolume = 0.75
        }, TestPetEngineFactory.CreateSkin(soundFiles: new[] { soundPath }));

        try
        {
            var played = await fixture.Engine.PlayTestSoundAsync();

            Assert.True(played);
            Assert.Single(fixture.AudioService.PlayedFiles);
            Assert.Equal(soundPath, fixture.AudioService.PlayedFiles[0]);
            Assert.Equal(0.75, fixture.AudioService.Volume);
        }
        finally
        {
            File.Delete(soundPath);
        }
    }

    [Fact]
    public async Task PlayTestSoundAsync_ReturnsFalseWhenSkinSoundFileIsMissing()
    {
        var missingSoundPath = Path.Combine(Path.GetTempPath(), $"quackduck-missing-{Guid.NewGuid():N}.wav");
        var fixture = await TestPetEngineFactory.CreateStartedAsync(
            PetSettings.Default with { SoundEnabled = true },
            TestPetEngineFactory.CreateSkin(soundFiles: new[] { missingSoundPath }));

        var played = await fixture.Engine.PlayTestSoundAsync();

        Assert.False(played);
        Assert.Empty(fixture.AudioService.PlayedFiles);
    }
}
