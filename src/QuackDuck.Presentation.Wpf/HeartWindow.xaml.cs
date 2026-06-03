using System;
using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Animation;
using System.Windows.Media.Imaging;

namespace QuackDuck.Presentation.Wpf;

public partial class HeartWindow : Window
{
    private const double RiseDistance = 32;
    private const double AnimationMilliseconds = 800;

    public HeartWindow(double screenX, double screenY, double size, string? imagePath = null)
    {
        InitializeComponent();
        var clampedSize = Math.Clamp(size, 8, 96);
        Width = clampedSize;
        Height = clampedSize + RiseDistance;
        HeartCanvas.Width = Width;
        HeartCanvas.Height = Height;
        HeartImage.Width = clampedSize;
        HeartImage.Height = clampedSize;
        Canvas.SetLeft(HeartImage, 0);
        Canvas.SetTop(HeartImage, RiseDistance);
        LoadHeartImage(imagePath);
        Left = screenX;
        Top = screenY - RiseDistance;
        Loaded += OnLoaded;
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        var rise = new DoubleAnimation
        {
            From = 0,
            To = -RiseDistance,
            Duration = TimeSpan.FromMilliseconds(AnimationMilliseconds),
            EasingFunction = new QuadraticEase { EasingMode = EasingMode.EaseOut }
        };
        HeartTransform.BeginAnimation(TranslateTransform.YProperty, rise);

        var fade = new DoubleAnimation
        {
            From = 1,
            To = 0,
            Duration = TimeSpan.FromMilliseconds(AnimationMilliseconds)
        };
        fade.Completed += (_, _) => Close();
        HeartImage.BeginAnimation(OpacityProperty, fade);
    }

    private void LoadHeartImage(string? imagePath)
    {
        if (string.IsNullOrWhiteSpace(imagePath) || !File.Exists(imagePath))
        {
            return;
        }

        var bitmap = new BitmapImage();
        bitmap.BeginInit();
        bitmap.CacheOption = BitmapCacheOption.OnLoad;
        bitmap.UriSource = new Uri(imagePath, UriKind.Absolute);
        bitmap.EndInit();
        bitmap.Freeze();
        HeartImage.Source = bitmap;
    }
}
