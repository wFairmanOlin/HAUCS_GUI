import tkinter as tk
from PIL import Image, ImageTk, ImageDraw

def generate_image(image_path):
    """Creates a simple generated image and saves it."""
    img = Image.new("RGB", (200, 200), "white")  # Create a blank image
    draw = ImageDraw.Draw(img)
    draw.rectangle((50, 50, 150, 150), fill="blue")  # Example shape
    img.save(image_path)  # Save generated image

def setup_gui(image_path):
    """Sets up the GUI with the generated image."""
    root = tk.Tk()
    root.title("Raspberry Pi GUI")
    root.geometry("480x320")

    # Load and display image
    img = Image.open(image_path)
    img = img.resize((200, 200))
    img = ImageTk.PhotoImage(img)

    image_label = tk.Label(root, image=img)
    image_label.pack(pady=20)
    
    text_frame = tk.Frame(root)
    text_frame.pack(side=tk.BOTTOM, pady=10)

    def create_text_field(frame, label_text):
        label = tk.Label(frame, text=label_text, font=("Arial", 12))
        label.pack()
        entry = tk.Entry(frame, width=30)
        entry.pack()
        return entry

    entry1 = create_text_field(text_frame, "Title 1")
    entry2 = create_text_field(text_frame, "Title 2")
    entry3 = create_text_field(text_frame, "Title 3")

    root.mainloop()

def main():
    """Main function to generate image and start GUI."""
    image_path = "generated_image.png"
    generate_image(image_path)
    setup_gui(image_path)

if __name__ == "__main__":
    main()