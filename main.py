"""
Self Driving Computer
"""
import os
import time
import base64
import json
import math


from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import message_dialog
from prompt_toolkit.styles import Style as PromptStyle
from colorama import Style as ColoramaStyle
from dotenv import load_dotenv
from PIL import ImageGrab, Image, ImageDraw, ImageFont
import matplotlib.font_manager as fm
import pyautogui

from openai import OpenAI


load_dotenv()

client = OpenAI()
client.api_key = os.getenv("OPENAI_API_KEY")


# Define style
style = PromptStyle.from_dict(
    {
        "dialog": "bg:#88ff88",
        "button": "bg:#ffffff #000000",
        "dialog.body": "bg:#44cc44 #ffffff",
        "dialog shadow": "bg:#003800",
    }
)


PROMPT_POSITION = """
From looking at a screenshot, your goal is to guess the X & Y location on the screen in order to fire a click event. The X & Y location are in percentage (%) of screen width and height.

Example are below.
__
Objective: Find a image of a banana
Guess: Click on the Window with an image of a banana in it. 
Location: {{ "x": "0.5", "y": "0.6", "justification": "I think the banana is in the middle of the screen" }} 
__
Objective: Write an email to Best buy and ask for computer support
Guess: Click on the email compose window in Outlook
Location: {{ "x": "0.2", "y": "0.1", "justification": "It looks like this is where the email compose window is" }} 
__
Objective: Open Spotify and play the beatles
Guess: Click on the search field in the Spotify app
Location: {{ "x": "0.2", "y": "0.9", "justification": "I think this is the search field." }}
__

IMPORTANT: Respond with nothing but the `{{ "x": "percent", "y": "percent",  "justification": "justificaiton here" }}` and do not comment additionally.

Here's where it gets a little complex. A previous function provided you a guess of what to click, but this function was blind so it may be wrong. 

Based on the objective below and the guess use your best judgement on what you should click to reach this objective. 
Objective: {objective}
Guess: {guess}
Location: 
"""


PROMPT_TYPE = """
You are a professional writer. Based on the objective below, decide what you should write. 

IMPORTANT: Respond directly with what you are going to write and nothing else!

Objective: {objective}
Writing:
"""

USER_QUESTION = "What would you like the computer to do?"

SYSTEM_PROMPT = """
You are a Self Operating Computer. You use the same visual and input interfaces (i.e. screenshot, click & type) as a human, except you are superhuman. 

You have an objective from the user and you will decide the exact click and keyboard type actions to accomplish that goal. 

You have the tools (i.e. functions) below to accomplish the task.

1. mouse_click - Move mouse and click
2. keyboard_type - Type on the keyboard
3. mac_search - Search for a program on Mac

Your instructions must be in JSON format in the format below. 

Let's look at each function. 

1. mouse_click

From looking at a screenshot, your goal is to guess the X & Y location on the screen in order to fire a click event. The X & Y location are in percentage (%) of screen width and height.

Examples are below.
__
Objective: Find a image of a banana
Action: {
    "action": "mouse_click",
    "arguments": {
        "x": "0.5", "y": "0.6"
    },
    "explanation": "Clicking the banana image on Google"
}
__
Objective: Write an email to Best buy and ask for computer support
Action: {
    "action": "mouse_click",
    "arguments": {
        "x": "0.2", "y": "0.1", 
    },
    "explanation": "Clicking on the email compose box in Outlook"
}


2. keyboard_type

You can use the screenshot as context to make sure the focus is on the right field, document, or window. This function let's you type into that field or document.

Example is below.
__
Objective: Write an email to Best buy and ask for computer support
Action: {
    "action": "keyboard_type",
    "arguments": {
        "type_value": "Hello Best Buy, I need help with my computer."
    },
    "explanation": "Typing the email"
}

3. mac_search

When you need to open a program you can use this function to search for a program on Mac. You can use the screenshot as context to see if the right program is already open. 

Example is below.
__
Objective: Open Spotify and play the beatles
Action: {
    "action": "mac_search",
    "arguments": {
        "type_value": "spotify"
    },
    "explanation": "Searching for spotify"
}

Finally, once you have completed the objective, write the following phase and only this phase: DONE

"""

USER_TOOL_PROMPT = """
Objective: {objective}
Action:
"""

# def agent_loop():


def format_click_prompt(objective, click_guess):
    return PROMPT_POSITION.format(objective=objective, guess=click_guess)


def format_reposition_mouse_prompt(objective, click_guess, original_location):
    return PROMPT_POSITION.format(
        objective=objective, guess=click_guess, original_location=original_location
    )


def get_next_action(messages):
    screen = ImageGrab.grab()

    # Save the image file
    screen.save("new_screenshot.png")

    with open("new_screenshot.png", "rb") as img_file:
        img_base64 = base64.b64encode(img_file.read()).decode("utf-8")

    messages = messages + [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Use this image to decide the next action"},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"},
                },
            ],
        }
    ]

    response = client.chat.completions.create(
        model="gpt-4-vision-preview",
        messages=messages,
    )

    return response.choices[0].message


def check_click_location():
    screen_width, screen_height = pyautogui.size()

    # Get current mouse position
    mouse_x, mouse_y = pyautogui.position()

    # Calculate the rectangle bounds (25% of the screen around the mouse)
    capture_width = screen_width * 0.25
    capture_height = screen_height * 0.25
    left = max(mouse_x - capture_width / 2, 0)
    top = max(mouse_y - capture_height / 2, 0)
    right = min(mouse_x + capture_width / 2, screen_width)
    bottom = min(mouse_y + capture_height / 2, screen_height)

    # Capture the specified portion of the screen
    screen = ImageGrab.grab(bbox=(left, top, right, bottom))

    # Save the image file
    screen.save("mouse_location_check.png")

    return False


def handle_click(
    objective,
    click_guess,
    x_percentage,
    y_percentage,
    content="",
    duration=0.5,
):
    # Get the size of the primary monitor
    screen_width, screen_height = pyautogui.size()

    # Calculate the x and y coordinates in pixels
    x_pixel = int(screen_width * float(x_percentage))
    y_pixel = int(screen_height * float(y_percentage))

    # Move to the position smoothly
    pyautogui.moveTo(x_pixel, y_pixel, duration=duration)

    correct_click_location, new_x_pixal, new_y_pixel = evaluate_mouse(
        objective, click_guess, content
    )
    print("correct_click_location", correct_click_location)

    if not correct_click_location:
        print("We need to reposition the mouse")
        print("new_x_pixal", new_x_pixal)
        print("new_y_pixel", new_y_pixel)
        x_pixel = new_x_pixal
        y_pixel = new_y_pixel
        pyautogui.moveTo(x_pixel, y_pixel, duration=duration)

    click_at_percentage(x_pixel, y_pixel)
    return "We clicked " + click_guess


def click_at_percentage(x_pixel, y_pixel, circle_radius=50, circle_duration=0.3):
    # Circular movement
    start_time = time.time()
    while time.time() - start_time < circle_duration:
        angle = ((time.time() - start_time) / circle_duration) * 2 * math.pi
        x = x_pixel + math.cos(angle) * circle_radius
        y = y_pixel + math.sin(angle) * circle_radius
        pyautogui.moveTo(x, y, duration=0.1)

    # Finally, click
    pyautogui.click(x_pixel, y_pixel)
    return "successfully clicked"


def evaluate_mouse(objective, click_guess, original_location):
    screen = ImageGrab.grab()

    # Save the image file
    screen.save("new_screenshot.png")

    with open("new_screenshot.png", "rb") as img_file:
        img_base64 = base64.b64encode(img_file.read()).decode("utf-8")

    reposition_click_prompt = format_reposition_mouse_prompt(
        objective, click_guess, original_location
    )

    response = client.chat.completions.create(
        model="gpt-4-vision-preview",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": reposition_click_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"},
                    },
                ],
            }
        ],
        max_tokens=300,
    )

    result = response.choices[0]
    content = result.message.content
    print("[evaluate_mouse] content", content)
    if content == "NONE":
        return True, 0, 0

    parsed_result = extract_json_from_string(content)

    return False, parsed_result["x"], parsed_result["y"]


def mouse_click(objective):
    print("[mouse_click] click_xy", click_xy)
    parsed_result = extract_json_from_string(click_xy)
    if parsed_result:
        handle_click(
            objective, click_guess, parsed_result["x"], parsed_result["y"], content
        )
        return "We clicked something, it may have been" + click_guess

    return "We failed to click" + click_guess


def add_labeled_grid_to_image(image_path, grid_interval):
    # Load the image
    image = Image.open(image_path)

    # Create a drawing object
    draw = ImageDraw.Draw(image)

    # Get the image size
    width, height = image.size

    # Get the path to a TrueType font included with matplotlib
    font_paths = fm.findSystemFonts(fontpaths=None, fontext="ttf")
    # Filter for specific font name (e.g., 'Arial.ttf')

    font_path = next((path for path in font_paths if "Arial" in path), None)
    if not font_path:
        raise RuntimeError(
            "Specific TrueType font not found; install the font or check the font name."
        )

    font_size = grid_interval / 4  # Adjust this size as needed
    font = ImageFont.truetype(font_path, size=font_size)

    # Define the estimated background size based on the font size
    background_width = (
        font_size * 3
    )  # Estimate that each character is approximately 3 times the font size wide
    background_height = (
        font_size  # The height of the background is the same as the font size
    )

    # Function to draw text with a white rectangle background
    def draw_label_with_background(position, text, draw, font, bg_width, bg_height):
        background_position = (
            position[0],
            position[1],
            position[0] + bg_width,
            position[1] + bg_height,
        )
        draw.rectangle(background_position, fill="white")
        draw.text((position[0] + 3, position[1]), text, fill="black", font=font)

    # Draw vertical lines at every `grid_interval` pixels
    for x in range(0, width, grid_interval):
        line = ((x, 0), (x, height))
        draw.line(line, fill="blue")
        # Add the label to the right of the line with a white background
        draw_label_with_background(
            (x + 2, 2), str(x), draw, font, background_width, background_height
        )

    # Draw horizontal lines at every `grid_interval` pixels
    for y in range(0, height, grid_interval):
        line = ((0, y), (width, y))
        draw.line(line, fill="blue")
        # Add the label below the line with a white background
        draw_label_with_background(
            (2, y + 2), str(y), draw, font, background_width, background_height
        )

    # Save the image with the grid
    image.save("screenshot_with_grid.png")


def add_labeled_cross_grid_to_image(image_path, grid_interval):
    # Load the image
    image = Image.open(image_path)

    # Create a drawing object
    draw = ImageDraw.Draw(image)

    # Get the image size
    width, height = image.size

    # Get the path to a TrueType font included with matplotlib
    font_paths = fm.findSystemFonts(fontpaths=None, fontext="ttf")
    # Filter for specific font name (e.g., 'Arial.ttf')
    font_path = next((path for path in font_paths if "Arial" in path), None)
    if not font_path:
        raise RuntimeError(
            "Specific TrueType font not found; install the font or check the font name."
        )

    font_size = grid_interval // 7  # Adjust this size as needed
    font = ImageFont.truetype(font_path, size=int(font_size))

    # Calculate the background size based on the font size
    # Reduce the background to be just larger than the text
    bg_width = int(font_size * 5)  # Adjust as necessary
    bg_height = int(font_size * 1.2)  # Adjust as necessary

    # Function to draw text with a white rectangle background
    def draw_label_with_background(position, text, draw, font, bg_width, bg_height):
        # Adjust the position based on the background size
        text_position = (position[0] + bg_width // 2, position[1] + bg_height // 2)
        # Draw the text background
        draw.rectangle(
            [position[0], position[1], position[0] + bg_width, position[1] + bg_height],
            fill="white",
        )
        # Draw the text
        draw.text(text_position, text, fill="black", font=font, anchor="mm")

    # Calculate the background size based on the font size

    # Draw vertical lines and labels at every `grid_interval` pixels
    for x in range(grid_interval, width, grid_interval):
        line = ((x, 0), (x, height))
        draw.line(line, fill="blue")
        for y in range(grid_interval, height, grid_interval):
            draw_label_with_background(
                (x - bg_width // 2, y - bg_height // 2),
                f"{x},{y}",
                draw,
                font,
                bg_width,
                bg_height,
            )

    # Draw horizontal lines - labels are already added with vertical lines
    for y in range(grid_interval, height, grid_interval):
        line = ((0, y), (width, y))
        draw.line(line, fill="blue")

    # Save the image with the grid
    image.save("screenshot_with_grid.png")


def keyboard_type(text):
    for char in text:
        pyautogui.write(char)
    return "successfully typed " + text


def mac_search(text):
    # Press and release Command and Space separately
    pyautogui.keyDown("command")
    pyautogui.press("space")
    pyautogui.keyUp("command")
    # Now type the text
    for char in text:
        pyautogui.write(char)

    time.sleep(1)
    pyautogui.press("enter")
    return "successfully opened " + text + " on Mac"


available_functions = {
    "mouse_click": mouse_click,
    "keyboard_type": keyboard_type,
    "mac_search": mac_search,
}  # only one function in this example, but you can have multiple


def main():
    message_dialog(
        title="Self Operating Computer",
        text="Ask a computer to do anything.",
        style=style,
    ).run()

    os.system("clear")  # Clears the terminal screen

    user_response = prompt(USER_QUESTION + "\n")

    system_prompt = {"role": "system", "content": SYSTEM_PROMPT}
    user_prompt = {
        "role": "user",
        "content": USER_TOOL_PROMPT.format(objective=user_response),
    }
    messages = [system_prompt, user_prompt]

    looping = True
    loop_count = 0

    while looping:
        time.sleep(2)
        response = get_next_action(messages)
        print("[main] response", response)

        content = response.content
        print("[main] content", content)

        messages.append(response)
        if content == "DONE":
            print("[main] DONE")
            looping = False
            break

        decision = json.loads(content)
        print("[main] decision", decision)
        action = decision.get("action")
        arguments = decision.get("arguments")

        if action == "mouse_click":
            click_xy = arguments
            function_response = mouse_click(click_xy)
        elif action == "keyboard_type":
            type_value = function_args.get("type_value")
            function_response = keyboard_type(type_value)
        elif action == "mac_search":
            type_value = function_args.get("type_value")
            function_response = mac_search(type_value)
        else:
            print("Something went wrong")

        loop_count += 1
        if loop_count > 10:
            looping = False


def extract_json_from_string(s):
    # print("extracting json from string", s)
    try:
        # Find the start of the JSON structure
        json_start = s.find("{")
        if json_start == -1:
            return None

        # Extract the JSON part and convert it to a dictionary
        json_str = s[json_start:]
        return json.loads(json_str)
    except Exception as e:
        print(f"Error parsing JSON: {e}")
        return None


if __name__ == "__main__":
    main()
