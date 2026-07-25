using System.Collections.ObjectModel;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

namespace LetterblackInferenceControl.Controls.Widgets;

public partial class MachineTopologyWidget : WidgetBase
{
    private readonly MainWindow _mainWindow;
    private readonly ObservableCollection<MachineDisplayItem> _machines = [];
    
    public MachineTopologyWidget(Widget data, MainWindow mainWindow) : base(data)
    {
        InitializeComponent();
        _mainWindow = mainWindow;
        MachineItemsControl.ItemsSource = _machines;
        LoadMachines();
        
        // Refresh every 10 seconds
        var timer = new System.Timers.Timer(10000);
        timer.Elapsed += async (s, e) => await RefreshAsync();
        timer.Start();
    }

    private async void LoadMachines()
    {
        try
        {
            var response = await _mainWindow.GetAsync<List<MachineProfile>>("/machines");
            _machines.Clear();
            foreach (var m in response)
            {
                _machines.Add(new MachineDisplayItem
                {
                    Id = m.Id,
                    Name = m.Name,
                    Address = m.Host,
                    Enabled = m.Enabled,
                    RpcEnabled = m.Rpc.Enabled,
                    StatusColor = m.Enabled ? Brushes.LightGreen : Brushes.Gray,
                    RpcButtonText = m.Rpc.Enabled ? "Stop RPC" : "Start RPC",
                    ToggleButtonText = m.Enabled ? "Disconnect" : "Connect",
                    ToggleButtonBg = m.Enabled ? "#3A171D" : "{StaticResource Accent}",
                    ToggleButtonFg = m.Enabled ? "#FECACA" : "#F8FAFC"
                });
            }
            MachineCount.Text = $"{_machines.Count(m => m.Enabled)}/{_machines.Count} online";
        }
        catch { /* Silently fail */ }
    }

    public override async Task RefreshAsync() => LoadMachines();

    private void AddMachine_Click(object sender, RoutedEventArgs e)
    {
        _mainWindow.OpenMachineDialog();
    }

    private async void TestMachine_Click(object sender, RoutedEventArgs e)
    {
        var button = sender as Button;
        var id = button?.Tag?.ToString();
        if (string.IsNullOrEmpty(id)) return;
        
        try
        {
            await _mainWindow.SendAsync<MachineTestResult>(HttpMethod.Post, $"/machines/{id}/test", new { });
            ShowToast($"Machine {id} tested successfully", "success");
        }
        catch (Exception ex)
        {
            ShowToast($"Test failed: {ex.Message}", "error");
        }
    }

    private async void ToggleRpc_Click(object sender, RoutedEventArgs e)
    {
        var button = sender as Button;
        var id = button?.Tag?.ToString();
        if (string.IsNullOrEmpty(id)) return;
        
        try
        {
            var machine = await _mainWindow.GetAsync<MachineProfile>($"/machines/{id}");
            machine.Rpc.Enabled = !machine.Rpc.Enabled;
            await _mainWindow.SendAsync<MachineProfile>(HttpMethod.Put, $"/machines/{id}", machine);
            await RefreshAsync();
            ShowToast($"RPC {(machine.Rpc.Enabled ? "started" : "stopped")}", "info");
        }
        catch (Exception ex)
        {
            ShowToast($"RPC toggle failed: {ex.Message}", "error");
        }
    }

    private async void ToggleMachine_Click(object sender, RoutedEventArgs e)
    {
        var button = sender as Button;
        var id = button?.Tag?.ToString();
        if (string.IsNullOrEmpty(id)) return;
        
        try
        {
            var machine = await _mainWindow.GetAsync<MachineProfile>($"/machines/{id}");
            machine.Enabled = !machine.Enabled;
            await _mainWindow.SendAsync<MachineProfile>(HttpMethod.Put, $"/machines/{id}", machine);
            await RefreshAsync();
            ShowToast($"Machine {(machine.Enabled ? "connected" : "disconnected")}", "info");
        }
        catch (Exception ex)
        {
            ShowToast($"Toggle failed: {ex.Message}", "error");
        }
    }
}

public class MachineDisplayItem
{
    public string Id { get; set; } = "";
    public string Name { get; set; } = "";
    public string Address { get; set; } = "";
    public bool Enabled { get; set; }
    public bool RpcEnabled { get; set; }
    public Brush StatusColor { get; set; } = Brushes.Gray;
    public string RpcButtonText { get; set; } = "Start RPC";
    public string ToggleButtonText { get; set; } = "Connect";
    public string ToggleButtonBg { get; set; } = "{StaticResource Accent}";
    public string ToggleButtonFg { get; set; } = "#F8FAFC";
}