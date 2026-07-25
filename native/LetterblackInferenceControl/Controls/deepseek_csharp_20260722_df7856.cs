using System.Windows;

namespace LetterblackInferenceControl.Controls;

public partial class FloatingWidgetWindow : Window
{
    public FloatingWidgetWindow(WidgetBase widget, string title = "Widget")
    {
        InitializeComponent();
        TitleText.Text = title;
        WidgetContent.Content = widget;
        
        // Make draggable
        MouseLeftButtonDown += (s, e) => DragMove();
    }

    private void Close_Click(object sender, RoutedEventArgs e)
    {
        Close();
    }
}