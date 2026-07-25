using System.Windows;
using System.Windows.Controls;

namespace LetterblackInferenceControl.Controls;

public abstract class WidgetBase : UserControl
{
    public Widget WidgetData { get; set; } = new();
    
    protected WidgetBase(Widget data)
    {
        WidgetData = data;
        Margin = new Thickness(4);
    }

    public virtual async Task RefreshAsync() { }
    public virtual void OnWorkspaceChanged() { }
    
    protected void ShowToast(string message, string type = "info")
    {
        // Fire a routed event that MainWindow handles
        var args = new RoutedEventArgs(ToastEvent, this) { Source = this };
        RaiseEvent(args);
    }

    public static readonly RoutedEvent ToastEvent = EventManager.RegisterRoutedEvent(
        "Toast", RoutingStrategy.Bubble, typeof(RoutedEventHandler), typeof(WidgetBase));
}