using System.Collections.ObjectModel;
using System.Text.Json;

namespace LetterblackInferenceControl.Models;

public class Workspace
{
    public string Id { get; set; } = "workspace-default";
    public string Name { get; set; } = "Inference Lab";
    public int LayoutVersion { get; set; } = 1;
    public string Mode { get; set; } = "operate";
    public WorkspaceGrid Grid { get; set; } = new();
    public ObservableCollection<Widget> Widgets { get; set; } = [];
    public WorkspaceNavigation Navigation { get; set; } = new();
    public WorkspaceTheme Theme { get; set; } = new();
    public long CreatedAt { get; set; }
    public long UpdatedAt { get; set; }
}

public class WorkspaceGrid
{
    public int Columns { get; set; } = 12;
    public int RowHeight { get; set; } = 72;
    public string Density { get; set; } = "comfortable";
}

public class Widget
{
    public string Id { get; set; } = "";
    public string Type { get; set; } = "";
    public WidgetPosition Position { get; set; } = new();
    public WidgetSize Size { get; set; } = new();
    public Dictionary<string, JsonElement> Settings { get; set; } = [];
    public bool Visibility { get; set; } = true;
}

public class WidgetPosition
{
    public int X { get; set; }
    public int Y { get; set; }
}

public class WidgetSize
{
    public int W { get; set; } = 4;
    public int H { get; set; } = 3;
}

public class WorkspaceNavigation
{
    public List<string> Hidden { get; set; } = [];
    public List<string> Order { get; set; } = 
        ["workspace", "models", "machines", "playground", "telemetry", "logs", "profiles", "extensions", "settings"];
}

public class WorkspaceTheme
{
    public string Name { get; set; } = "blueprint-dark";
}