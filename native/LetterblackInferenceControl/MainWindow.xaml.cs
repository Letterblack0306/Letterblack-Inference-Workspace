private void AddWidget_Click(object sender, RoutedEventArgs e)
{
    // Show a popup to select widget type
    var types = new[] { "active-model", "machine-topology", "gpu-telemetry", "request-table" };
    var dialog = new WidgetPickerDialog(types);
    
    if (dialog.ShowDialog() == true)
    {
        var selectedType = dialog.SelectedType;
        var widgetData = new Widget 
        { 
            Id = $"widget-{selectedType}-{Guid.NewGuid():N}", 
            Type = selectedType,
            Size = new WidgetSize { W = 4, H = 3 }
        };
        
        // Add to workspace
        var widget = CreateWidget(widgetData);
        WorkspaceContainer.Widgets.Add(new WidgetItem { Widget = widget, Width = 240, Height = 216 });
        
        // Optional: Open as floating window
        var floatingWindow = new FloatingWidgetWindow(widget, selectedType);
        floatingWindow.Show();
    }
}

private async void SaveLayout_Click(object sender, RoutedEventArgs e)
{
    try
    {
        var workspace = new Workspace
        {
            Id = "workspace-default",
            Name = "Inference Lab",
            Widgets = new ObservableCollection<Widget>()
        };
        
        // Convert workspace widgets to data
        foreach (var item in WorkspaceContainer.Widgets)
        {
            workspace.Widgets.Add(item.Widget.WidgetData);
        }
        
        await SendAsync<Workspace>(HttpMethod.Put, "/workspaces/workspace-default", workspace);
        StatusText.Text = "Layout saved successfully.";
        ShowToast("Layout saved", "success");
    }
    catch (Exception ex)
    {
        StatusText.Text = $"Save failed: {ex.Message}";
        ShowToast($"Save failed: {ex.Message}", "error");
    }
}

private void ShowToast(string message, string type = "info")
{
    // Simple toast notification
    var toast = new ToastNotification(message, type);
    toast.Show();
}