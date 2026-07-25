using System.Windows;
using System.Windows.Controls;

namespace LetterblackInferenceControl.Controls.Widgets;

public partial class ActiveModelWidget : WidgetBase
{
    private readonly MainWindow _mainWindow;
    
    public ActiveModelWidget(Widget data, MainWindow mainWindow) : base(data)
    {
        InitializeComponent();
        _mainWindow = mainWindow;
    }

    private void SelectModel_Click(object sender, RoutedEventArgs e)
    {
        _mainWindow.NavigateTo("models");
    }

    private async void Start_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var response = await _mainWindow.SendAsync<JobRecord>(HttpMethod.Post, "/runtime/start", new { modelId = "selected" });
            StatusBadge.Text = "⟳ Starting...";
            StatusBadge.Foreground = System.Windows.Media.Brushes.Gold;
        }
        catch (Exception ex)
        {
            ShowToast($"Start failed: {ex.Message}", "error");
        }
    }

    private async void Stop_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            await _mainWindow.SendAsync<JobRecord>(HttpMethod.Post, "/runtime/stop", new { force = false });
            StatusBadge.Text = "● Stopped";
            StatusBadge.Foreground = System.Windows.Media.Brushes.Gray;
            ModelName.Text = "No model loaded";
        }
        catch (Exception ex)
        {
            ShowToast($"Stop failed: {ex.Message}", "error");
        }
    }

    public override async Task RefreshAsync()
    {
        try
        {
            var runtime = await _mainWindow.GetAsync<JsonElement>("/runtime/status");
            var state = runtime.GetProperty("state").GetString();
            
            if (state == "running")
            {
                StatusBadge.Text = "● Running";
                StatusBadge.Foreground = System.Windows.Media.Brushes.LightGreen;
                var modelId = runtime.GetProperty("activeModelId").GetString();
                ModelName.Text = modelId ?? "Unknown model";
            }
            else
            {
                StatusBadge.Text = "● Stopped";
                StatusBadge.Foreground = System.Windows.Media.Brushes.Gray;
                ModelName.Text = "No model loaded";
            }
        }
        catch { /* Silently fail */ }
    }
}