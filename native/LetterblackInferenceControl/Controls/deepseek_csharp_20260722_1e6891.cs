using System.Collections.ObjectModel;
using System.Windows.Controls;

namespace LetterblackInferenceControl.Controls;

public partial class WorkspaceContainer : UserControl
{
    private readonly MainWindow _mainWindow;
    public ObservableCollection<WidgetItem> Widgets { get; set; } = [];

    public WorkspaceContainer(MainWindow mainWindow)
    {
        InitializeComponent();
        _mainWindow = mainWindow;
        WidgetItemsControl.ItemsSource = Widgets;
    }

    public async Task LoadWorkspaceAsync(string workspaceId = "workspace-default")
    {
        try
        {
            var workspace = await _mainWindow.GetAsync<Workspace>($"/workspaces/{workspaceId}");
            Widgets.Clear();

            foreach (var widgetData in workspace.Widgets.Where(w => w.Visibility))
            {
                var widget = CreateWidget(widgetData);
                var width = widgetData.Size.W * 60; // 60px per column
                var height = widgetData.Size.H * 72; // 72px per row
                
                Widgets.Add(new WidgetItem 
                { 
                    Widget = widget, 
                    Width = width, 
                    Height = height 
                });
            }
        }
        catch
        {
            // Fallback to default widgets
            LoadDefaultWorkspace();
        }
    }

    private void LoadDefaultWorkspace()
    {
        Widgets.Clear();
        
        var defaultWidgets = new[]
        {
            new { type = "active-model", w = 8, h = 3 },
            new { type = "machine-topology", w = 4, h = 3 },
            new { type = "gpu-telemetry", w = 7, h = 3 },
            new { type = "request-table", w = 5, h = 3 }
        };

        foreach (var w in defaultWidgets)
        {
            var widgetData = new Widget { Id = $"widget-{w.type}", Type = w.type, Size = new WidgetSize { W = w.w, H = w.h } };
            var widget = CreateWidget(widgetData);
            Widgets.Add(new WidgetItem { Widget = widget, Width = w.w * 60, Height = w.h * 72 });
        }
    }

    private WidgetBase CreateWidget(Widget data)
    {
        return data.Type switch
        {
            "active-model" => new ActiveModelWidget(data, _mainWindow),
            "machine-topology" => new MachineTopologyWidget(data, _mainWindow),
            "gpu-telemetry" => new GPUTelemetryWidget(data, _mainWindow),
            "request-table" => new RequestTableWidget(data, _mainWindow),
            _ => new PlaceholderWidget(data, _mainWindow)
        };
    }
}

public class WidgetItem
{
    public WidgetBase Widget { get; set; }
    public double Width { get; set; }
    public double Height { get; set; }
}