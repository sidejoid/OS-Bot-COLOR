'''
The RuneLiteBot class contains properties and functions that are common across all RuneLite-based clients. This class
should be inherited by additional abstract classes representing all bots for a specific game (E.g., Alora, OSRS, etc.).

To determine Thresholds for finding contours: https://pinetools.com/threshold-image
For converting RGB to HSV:
    https://stackoverflow.com/questions/10948589/choosing-the-correct-upper-and-lower-hsv-boundaries-for-color-detection-withcv/48367205#48367205
'''
from abc import ABCMeta
from deprecated import deprecated
from model.bot import Bot, BotStatus
from model.window import Window
from typing import List
from utilities.geometry import Rectangle, Point
from utilities.runelite_cv import isolate_colors
import numpy as np
import pyautogui as pag
import random as rd
import time
import utilities.bot_cv as bcv
import utilities.runelite_cv as rcv


class RuneLiteWindow(Window):
    def __init__(self, window_title: str) -> None:
        super().__init__(window_title, padding_top=26, padding_left=0)
    
    # Override
    def resize(self, width: int = 773, height: int = 534) -> None:
        '''
        Resizes the client window. Default size is 773x534 (minsize of fixed layout).
        Args:
            width: The width to resize the window to.
            height: The height to resize the window to.
        '''
        if client := self.window:
            client.size = (width, height)

    # === Rectangles ===
    # The following rects are used to isolate specific areas of the client window.
    # Their positions were identified when game client was in fixed layout & anchored to the screen origin.
    def rect_current_action(self) -> Rectangle:
        '''
        Returns a Rectangle outlining the 'current action' area of the game view.
        E.g., Woodcutting plugin, Opponent Information plugin (<name of NPC>), etc.
        '''
        return Rectangle.from_points(Point(13, 51), Point(140, 73), self.position())


class RuneLiteBot(Bot, metaclass=ABCMeta):

    win: RuneLiteWindow = None

    # --- Notable Colors [R, G, B] ---
    BLUE = [0, 255, 255]
    PURPLE = [255, 170, 0]
    PINK = [255, 0, 231]
    GREEN = [0, 255, 0]
    RED = [255, 0, 0]

    def __init__(self, title, description, window: Window = RuneLiteWindow("RuneLite")) -> None:
        super().__init__(title, description, window)

    def drop_inventory(self, skip_rows: int = 0, skip_slots: list[int] = None) -> None:
        '''
        Drops all items in the inventory.
        Args:
            skip_rows: The number of rows to skip before dropping.
            skip_slots: The indices of slots to avoid dropping.
        '''
        self.log_msg("Dropping inventory...")
        # Determine slots to skip
        if skip_slots is None:
            skip_slots = []
        if skip_rows > 0:
            row_skip = list(range(skip_rows*4))
            skip_slots = np.unique(row_skip + skip_slots)
        # Start dropping
        pag.keyDown("shift")
        for i, slot in enumerate(self.win.inventory_slots()):
            if not self.status_check_passed():
                pag.keyUp("shift")
                return
            if i in skip_slots:
                continue
            self.mouse.move_to((slot[0], slot[1]),
                                targetPoints=rd.randint(10, 15),
                                knotsCount=1,
                                distortionMeanv=0.5,
                                offsetBoundaryY=40,
                                offsetBoundaryX=40)
            time.sleep(0.05)
            pag.click()
        pag.keyUp("shift")

    def friends_nearby(self) -> bool:
        '''
        Checks the minimap for green dots to indicate friends nearby.
        Returns:
            True if friends are nearby, False otherwise.
        '''
        # screenshot minimap
        minimap = bcv.screenshot(self.win.rect_minimap())
        only_friends = rcv.isolate_colors(minimap, [self.GREEN])
        #bcv.save_image("minimap_friends.png", only_friends)
        mean = only_friends.mean(axis=(0, 1))
        return mean != 0.0

    def get_hp(self) -> int:
        """
        Gets the HP value of the player.
        Returns:
            The HP of the player, or None if not found.
        """
        res = bcv.get_numbers_in_rect(self.win.rect_hp(), True)
        print(res)
        return None if res is None else res[0]

    def get_prayer(self) -> int:
        """
        Gets the prayer value of the player.
        Returns:
            The prayer value of the player, or None if not found.
        """
        res = bcv.get_numbers_in_rect(self.win.rect_prayer(), True)
        print(res)
        return None if res is None else res[0]

    def logout(self):
        '''
        Logs player out.
        '''
        self.log_msg("Logging out...")
        self.mouse.move_to(self.win.cp_tab(11))
        pag.click()
        time.sleep(1)
        self.mouse.move_rel(0, -53, 3)  # Logout button
        pag.click()
    
    def move_camera_up(self):
        '''
        Moves the camera up.
        '''
        # Position the mouse somewhere on the game view
        self.mouse.move_to(Point(self.win.rect_game_view().left + 20,
                                 self.win.rect_game_view().top + 20))
        pag.keyDown('up')
        time.sleep(2)
        pag.keyUp('up')
        time.sleep(0.5)

    def is_in_combat(self) -> bool:
        '''
        Returns whether the player is in combat. This is achieved by checking if text exists in the RuneLite opponent info
        section in the game view, and if that text indicates an NPC is out of HP.
        '''
        result = bcv.get_text_in_rect(self.win.rect_current_action())
        return result.strip() != ""
    
    def is_player_doing_action(self, action: str):
        '''
        Returns whether the player is doing the given action.
        Args:
            action: The action to check for.
        Returns:
            True if the player is doing the given action, False otherwise.
        Example:
            if self.is_player_doing_action("Woodcutting"):
                print("Player is woodcutting!")
        '''
        return bcv.search_text_in_rect(self.win.rect_current_action(), [action], ["not", "nof", "nol"])

    def has_hp_bar(self) -> bool:
        '''
        Returns whether the player has an HP bar above their head.
        This function only works when the game camera is all the way up.
        '''
        # Position of character relative to the screen
        char_pos = self.win.rect_game_view().get_center()

        # Make a rectangle around the character
        offset = 30
        char_rect = Rectangle.from_points(Point(char_pos.x - offset, char_pos.y - offset*2),
                                          Point(char_pos.x + offset, char_pos.y))
        # Take a screenshot of rect
        char_screenshot = bcv.screenshot(char_rect)
        # Isolate HP bars in that rectangle
        hp_bars = isolate_colors(char_screenshot, [self.RED, self.GREEN])
        # If there are any HP bars, return True
        return hp_bars.mean(axis=(0, 1)) != 0.0

    # --- NPC/Object Detection ---
    def attack_first_tagged(self) -> bool:
        '''
        Attacks the first-seen tagged NPC that is not already in combat.
        Args:
            game_view: The rectangle to search in.
        Returns:
            True if an NPC attack was attempted, False otherwise.
        '''
        game_view = self.win.rect_game_view()
        img_game_view = bcv.screenshot(game_view)
        # Isolate colors in image
        img_npcs = rcv.isolate_colors(img_game_view, [self.BLUE])
        img_hp_bars = rcv.isolate_colors(img_game_view, [self.GREEN, self.RED])
        # Locate potential NPCs in image by determining contours
        contours = rcv.get_contours(img_npcs)
        # Click center pixel of non-combatting NPCs
        for cnt in contours:
            try:
                center, top = rcv.get_contour_positions(cnt)
            except Exception:
                print("An NPC does not have complete outline. Disregarding. (This is normal)")
                continue
            if not rcv.is_point_obstructed(center, img_hp_bars):
                self.mouse.move_to(Point(center.x + game_view.left, center.y + game_view.top))
                pag.click()
                return True
        self.log_msg("No tagged NPCs found that aren't in combat.")
        return False

    def get_nearest_tagged_NPC(self, include_in_combat: bool = False) -> Point:
        '''
        Returns the nearest tagged NPC.
        Args:
            game_view: The rectangle to search in.
        Returns:
            The center point of the nearest tagged NPC, or None if none found.
        '''
        game_view = self.win.rect_game_view()
        img_game_view = bcv.screenshot(game_view)
        # Isolate colors in image
        img_npcs = rcv.isolate_colors(img_game_view, [self.BLUE])
        img_hp_bars = rcv.isolate_colors(img_game_view, [self.GREEN, self.RED])
        # Locate potential NPCs in image by determining contours
        contours = rcv.get_contours(img_npcs)
        # Get center pixels of non-combatting NPCs
        centers = []
        for cnt in contours:
            try:
                center, _ = rcv.get_contour_positions(cnt)
            except Exception:
                print("An NPC does not have complete outline. Disregarding. (This is normal)")
                continue
            if not include_in_combat and not rcv.is_point_obstructed(center, img_hp_bars) or include_in_combat:
                centers.append((center.x, center.y))
        if not centers:
            print("No tagged NPCs found.")
            return None
        dims = img_hp_bars.shape  # (height, width, channels)
        nearest = self.__get_nearest_point(Point(int(dims[1] / 2), int(dims[0] / 2)), centers)
        return Point(nearest.x + game_view.left, nearest.y + game_view.top)

    def get_all_tagged_in_rect(self, rect: Rectangle, color: List[int]) -> list:
        '''
        Finds all contours on screen of a particular color and returns a list of center Points for each.
        Args:
            rect: The rectangle to search in.
            color: The color to search for [R,G,B].
        Returns:
            A list of center Points.
        '''
        img_rect = bcv.screenshot(rect)
        bcv.save_image("img_rect.png", img_rect)
        img_isolated = rcv.isolate_colors(img_rect, [color])
        bcv.save_image("img_isolated.png", img_isolated)
        contours = rcv.get_contours(img_isolated)
        centers = []
        for cnt in contours:
            try:
                center, _ = rcv.get_contour_positions(cnt)
            except Exception:
                print("Cannot find complete outline of tagged object. Disregarding. (This is normal)")
                continue
            centers.append(Point(center.x + rect.left, center.y + rect.top))
        return centers
    
    def get_nearest_tag(self, color: List[int]) -> Point:
        '''
        Finds the nearest contour of a particular color within the game view to the character and returns its center Point.
        Args:
            rect: The rectangle to search in.
            color: The color to search for [R,G,B].
        Returns:
            The center Point of the nearest contour, or None if none found.
        '''
        rect = self.win.rect_game_view()
        centers = self.get_all_tagged_in_rect(rect, color)
        return self.__get_nearest_point(rect.get_center(), centers) if centers else None
        
    def __get_nearest_point(self, point: Point, points: list) -> Point:
        '''
        Returns the nearest point in a list of (x, y) coordinates.
        Args:
            point: The point to compare to.
            points: The list of (x, y) coordinates to compare.
        Returns:
            The closest point in the list.
        '''
        point = (point.x, point.y)
        nodes = np.asarray(points)
        dist_2 = np.sum((nodes - point) ** 2, axis=1)
        p = np.argmin(dist_2)
        return Point(points[p][0], points[p][1])

    # --- Client Settings ---
    def __open_display_settings(self) -> bool:
        '''
        Opens the display settings for the game client.
        Returns:
            True if the settings were opened, False if an error occured.
        '''
        client_rect = self.win.rectangle()
        cp_settings_selected = bcv.search_img_in_rect(f"{bcv.BOT_IMAGES}/cp_settings_selected.png",
                                                      client_rect,
                                                      precision=0.95)
        cp_settings = bcv.search_img_in_rect(f"{bcv.BOT_IMAGES}/cp_settings.png",
                                             client_rect,
                                             precision=0.95)
        if cp_settings_selected is None and cp_settings is None:
            self.log_msg("Could not find settings button.")
            return False
        elif cp_settings is not None and cp_settings_selected is None:
            self.mouse.move_to(cp_settings)
            pag.click()
        time.sleep(0.5)
        display_tab = bcv.search_img_in_rect(f"{bcv.BOT_IMAGES}/cp_settings_display_tab.png", client_rect)
        if display_tab is None:
            self.log_msg("Could not find the display settings tab.")
            return False
        self.mouse.move_to(display_tab)
        pag.click()
        time.sleep(0.5)
        return True

    def did_set_layout_fixed(self) -> bool:
        '''
        Attempts to set the client's layout to "Fixed - Classic layout".
        Returns:
            True if the layout was set, False if an issue occured.
        '''
        self.log_msg("Setting layout to Fixed - Classic layout.")
        time.sleep(0.3)
        if not self.__open_display_settings():
            return False
        time.sleep(0.3)
        layout_dropdown = bcv.search_img_in_rect(f"{bcv.BOT_IMAGES}/cp_settings_dropdown.png", self.win.rectangle())
        if layout_dropdown is None:
            self.log_msg("Could not find the layout dropdown.")
            return False
        self.mouse.move_to(layout_dropdown)
        pag.click()
        time.sleep(0.8)
        self.mouse.move_rel(-77, 19)
        pag.click()
        time.sleep(1.5)
        return True

    @deprecated(reason="This method is no longer needed for RuneLite games that can launch with arguments through the OSBC client.")
    def logout_runelite(self):
        '''
        Identifies the RuneLite logout button and clicks it.
        '''
        self.log_msg("Logging out of RuneLite...")
        rl_login_icon = bcv.search_img_in_rect(f"{bcv.BOT_IMAGES}/runelite_logout.png", self.win.rectangle(), precision=0.9)
        if rl_login_icon is not None:
            self.mouse.move_to(rl_login_icon)
            pag.click()
            time.sleep(0.2)
            pag.press('enter')
            time.sleep(1)

    def set_camera_zoom(self, percentage: int) -> bool:
        '''
        Sets the camera zoom level.
        Args:
            percentage: The percentage of the camera zoom level to set.
        Returns:
            True if the zoom level was set, False if an issue occured.
        '''
        if percentage < 1:
            percentage = 1
        elif percentage > 100:
            percentage = 100
        self.log_msg(f"Setting camera zoom to {percentage}%...")
        time.sleep(0.3)
        if not self.__open_display_settings():
            return False
        time.sleep(0.3)
        zoom_start = 611
        zoom_end = 708
        x = int((percentage / 100) * (zoom_end - zoom_start) + zoom_start)
        client_pos = self.win.position()
        self.mouse.move_to(Point(x + client_pos.x, 345 + client_pos.y))
        pag.click()
        return True

    # --- Setup Functions ---
    def setup_client(self, set_layout_fixed: bool = True, logout_runelite: bool = False) -> None:
        # sourcery skip: merge-nested-ifs
        '''
        Configures a RuneLite client window. This function logs messages to the script output log.
        Args:
            set_layout_fixed: Whether or not to set the layout to "Fixed - Classic layout" (default=True).
            logout_runelite: Whether or not to logout of RuneLite (not necessary when launching game via OSBC) (default=False).
        '''
        self.log_msg("Configuring client window...")

        # Set layout to fixed
        if set_layout_fixed:
            if not self.did_set_layout_fixed():  # if layout setup failed
                if pag.confirm("Could not set layout to fixed. Continue anyway?") == "Cancel":
                    self.set_status(BotStatus.STOPPED)
                    return
        # Ensure user is logged out of RuneLite
        if logout_runelite:
            self.logout_runelite()
        # Resize client window
        self.win.resize()
        self.log_msg("Client window configured.")
