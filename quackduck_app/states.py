import logging
import random
import time
from typing import TYPE_CHECKING

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QMouseEvent

if TYPE_CHECKING:  # pragma: no cover - avoids circular imports at runtime
    from .duck import Duck


class State:
    def __init__(self, duck: "Duck") -> None:
        self.duck = duck

    def enter(self) -> None:
        raise NotImplementedError

    def update_animation(self) -> None:
        raise NotImplementedError

    def update_position(self) -> None:
        raise NotImplementedError

    def exit(self) -> None:
        raise NotImplementedError

    def handle_mouse_press(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self.duck:
                self.duck.change_state(DraggingState(self.duck), event)
        elif event.button() == QtCore.Qt.MouseButton.RightButton:
            if self.duck:
                self.duck.change_state(JumpingState(self.duck))

    def handle_mouse_release(self, event: QMouseEvent) -> None:
        pass

    def handle_mouse_move(self, event: QMouseEvent) -> None:
        pass


class RunState(State):
    def __init__(self, duck):
        super().__init__(duck)
        self.start_time = None
        self.duration = random.uniform(60, 120)  # 60-120 sec
        self.speed_multiplier = 2  # same as in PlayfulState

    def enter(self):
        self.start_time = time.time()
        frames = self.duck.resources.get_animation_frames_by_name("running")
        if not frames:
            frames = self.duck.resources.get_animation_frames_by_name("walk")
        if not frames:
            frames = self.duck.resources.get_animation_frames_by_name("idle")
        self.frames = frames or []
        self.frame_index = 0

        self.prev_speed = self.duck.duck_speed
        self.duck.duck_speed = self.duck.base_duck_speed * self.speed_multiplier * (self.duck.pet_size / 3)
        self.update_frame()

    def update_animation(self):
        if not self.frames:
            return
        self.frame_index = (self.frame_index + 1) % len(self.frames)
        self.update_frame()

    def update_position(self):
        elapsed = time.time() - self.start_time
        if elapsed > self.duration:
            self.duck.change_state(WalkingState(self.duck))
            return

        if self.duck.is_listening:
            return

        self.duck.duck_x += self.duck.duck_speed * self.duck.direction
        if self.duck.duck_x < 0 or self.duck.duck_x + self.duck.duck_width > self.duck.screen_width:
            self.duck.change_direction()
        self.duck.move(int(self.duck.duck_x), int(self.duck.duck_y))

    def exit(self):
        self.duck.duck_speed = self.prev_speed

    def update_frame(self):
        if not self.frames:
            return
        frame = self.frames[self.frame_index]
        if not self.duck.facing_right:
            frame = frame.transformed(QtGui.QTransform().scale(-1, 1))
        self.duck.current_frame = frame
        self.duck.update()


class AttackState(State):
    def __init__(self, duck, return_state=None):
        super().__init__(duck)
        self.return_state = return_state
        self.animation_finished = False

    def enter(self):
        self.frames = self.duck.resources.get_animation_frames_by_name("attack") or self.duck.resources.get_animation_frames_by_name("idle")
        self.frame_index = 0
        self.update_frame()
        self.animation_finished = False

    def update_animation(self):
        if self.frames:
            if self.frame_index < len(self.frames) - 1:
                self.frame_index += 1
                self.update_frame()
            else:
                if not self.animation_finished:
                    self.animation_finished = True
                    if self.return_state:
                        self.duck.change_state(self.return_state)
                    else:
                        self.duck.change_state(WalkingState(self.duck))

    def update_position(self):
        pass

    def exit(self):
        self.duck.facing_right = self.duck.direction == 1
        if isinstance(self.duck.state, (WalkingState, IdleState)):
            self.duck.state.frame_index = 0
            self.duck.state.update_frame()

    def update_frame(self):
        if self.frames:
            frame = self.frames[self.frame_index]
            if not self.duck.facing_right:
                frame = frame.transformed(QtGui.QTransform().scale(-1, 1))
            self.duck.current_frame = frame
            self.duck.update()

    def handle_mouse_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.duck.stop_current_state()
            self.duck.change_state(DraggingState(self.duck), event)

    def handle_mouse_move(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.duck.stop_current_state()
            self.duck.change_state(DraggingState(self.duck), event)


class LandingState(State):
    def __init__(self, duck, next_state=None):
        super().__init__(duck)
        self.next_state = next_state or WalkingState(duck)

    def enter(self):
        frames = self.duck.resources.get_animation_frames_by_name("land")
        if not frames:
            frames = self.duck.resources.get_animation_frames_by_name("idle")
        self.frames = frames or []
        self.frame_index = 0
        self.update_frame()

    def update_animation(self):
        if not self.frames:
            self.duck.change_state(self.next_state)
            return
        if self.frame_index < len(self.frames) - 1:
            self.frame_index += 1
            self.update_frame()
        else:
            self.duck.change_state(self.next_state)

    def update_position(self):
        pass

    def exit(self):
        pass

    def update_frame(self):
        if not self.frames:
            return
        frame = self.frames[self.frame_index]
        if not self.duck.facing_right:
            frame = frame.transformed(QtGui.QTransform().scale(-1, 1))
        self.duck.current_frame = frame
        self.duck.update()


class ListeningState(State):
    def enter(self):
        self.duck.is_listening = True
        frames = self.duck.resources.get_animation_frames_by_name("listen")
        if not frames:
            frames = self.duck.resources.get_animation_frames_by_name("idle")
        self.frames = frames or []
        self.frame_index = 0
        self.update_frame()
        logging.info("ListeningState: Entered.")

    def update_animation(self):
        if not self.frames:
            return
        self.frame_index = (self.frame_index + 1) % len(self.frames)
        self.update_frame()

    def update_position(self):
        pass

    def exit(self):
        self.duck.is_listening = False
        logging.info("ListeningState: Exited.")

    def update_frame(self):
        if not self.frames:
            return
        frame = self.frames[self.frame_index]
        if not self.duck.facing_right:
            frame = frame.transformed(QtGui.QTransform().scale(-1, 1))
        self.duck.current_frame = frame
        self.duck.update()

    def handle_mouse_press(self, event):
        super().handle_mouse_press(event)

    def handle_mouse_move(self, event):
        if event.buttons() & QtCore.Qt.MouseButton.LeftButton:
            self.duck.is_listening = False
            self.duck.change_state(DraggingState(self.duck), event)
            logging.info("ListeningState: Entering DraggingState due to moving.")

    def handle_mouse_release(self, event):
        pass


class WalkingState(State):
    def enter(self):
        frames = self.duck.resources.get_animation_frames_by_name("walk")
        if not frames:
            frames = self.duck.resources.get_animation_frames_by_name("idle")
        self.frames = frames or []
        self.frame_index = 0
        self.update_frame()

        self.start_time = time.time()
        self.walk_duration = random.uniform(5, 15)

    def update_animation(self):
        if not self.frames:
            return
        self.frame_index = (self.frame_index + 1) % len(self.frames)
        self.update_frame()

    def update_position(self):
        if self.duck.is_listening:
            return

        self.duck.duck_x += self.duck.duck_speed * self.duck.direction
        if self.duck.duck_x < 0 or self.duck.duck_x + self.duck.duck_width > self.duck.screen_width:
            self.duck.change_direction()

        self.duck.move(int(self.duck.duck_x), int(self.duck.duck_y))
        elapsed_time = time.time() - self.start_time
        if elapsed_time > self.walk_duration:
            if not isinstance(self.duck.state, (FallingState, DraggingState)):
                self.duck.change_state(IdleState(self.duck))

    def exit(self):
        if hasattr(self, "cursor_shake_timer"):
            self.cursor_shake_timer.stop()
            self.cursor_shake_timer = None

    def update_frame(self):
        if not self.frames:
            return
        frame = self.frames[self.frame_index]
        if not self.duck.facing_right:
            frame = frame.transformed(QtGui.QTransform().scale(-1, 1))
        self.duck.current_frame = frame
        self.duck.update()


class FallingState(State):
    def __init__(self, duck, play_animation=True, return_state=None):
        super().__init__(duck)
        self.play_animation = play_animation
        self.return_state = return_state or WalkingState(duck)

    def enter(self):
        if self.play_animation:
            frames = self.duck.resources.get_animation_frames_by_name("fall")
            if not frames:
                frames = self.duck.resources.get_animation_frames_by_name("idle")
        else:
            frames = [self.duck.current_frame] if self.duck.current_frame else []
        self.frames = frames or []
        self.frame_index = 0
        self.vertical_speed = 0
        self.update_frame()

    def update_animation(self):
        if not self.play_animation or not self.frames:
            return
        if self.frame_index < len(self.frames) - 1:
            self.frame_index += 1
            self.update_frame()

    def update_position(self):
        self.vertical_speed += 1
        self.duck.duck_y += self.vertical_speed

        if self.duck.duck_y + self.duck.duck_height >= self.duck.ground_level:
            self.duck.duck_y = self.duck.ground_level - self.duck.duck_height
            self.vertical_speed = 0
            self.duck.move(int(self.duck.duck_x), int(self.duck.duck_y))
            self.duck.change_state(LandingState(self.duck, next_state=self.return_state))
        else:
            self.duck.move(int(self.duck.duck_x), int(self.duck.duck_y))

    def exit(self):
        pass

    def update_frame(self):
        if not self.frames:
            return
        frame = self.frames[self.frame_index]
        if not self.duck.facing_right:
            frame = frame.transformed(QtGui.QTransform().scale(-1, 1))
        self.duck.current_frame = frame
        self.duck.update()


class DraggingState(State):
    def enter(self):
        frames = self.duck.resources.get_animation_frames_by_name("fall")
        if not frames:
            frames = self.duck.resources.get_animation_frames_by_name("idle")
        self.frames = frames or []
        self.frame_index = 0
        self.update_frame()

        if self.duck.name_window:
            self.duck.name_window.hide()

    def update_animation(self):
        if not self.frames:
            return
        if self.frame_index < len(self.frames) - 1:
            self.frame_index += 1
            self.update_frame()

    def update_position(self):
        pass

    def exit(self):
        if self.duck.name_window and self.duck.show_name and self.duck.pet_name.strip():
            self.duck.name_window.show()

    def update_frame(self):
        if not self.frames:
            return
        frame = self.frames[self.frame_index]
        if not self.duck.facing_right:
            frame = frame.transformed(QtGui.QTransform().scale(-1, 1))
        self.duck.current_frame = frame
        self.duck.update()

    def handle_mouse_press(self, event):
        self.offset = event.pos()

    def handle_mouse_move(self, event):
        new_pos = QtGui.QCursor.pos() - self.offset
        self.duck.duck_x = new_pos.x()
        self.duck.duck_y = new_pos.y()
        self.duck.move(int(self.duck.duck_x), int(self.duck.duck_y))

        if self.duck.name_window and self.duck.show_name and self.duck.pet_name.strip():
            self.duck.name_window.update_position()

    def handle_mouse_release(self, event):
        self.duck.change_state(FallingState(self.duck, play_animation=False, return_state=WalkingState(self.duck)))


class JumpingState(State):
    def __init__(self, duck, return_state=None):
        super().__init__(duck)
        self.return_state = return_state
        self.vertical_speed = -15
        self.is_falling = False

    def enter(self):
        self.duck.facing_right = self.duck.direction == 1
        jump_frames = self.duck.resources.get_animation_frames_by_name("jump")
        if not jump_frames:
            jump_frames = self.duck.resources.get_animation_frames_by_name("idle")
        fall_frames = self.duck.resources.get_animation_frames_by_name("fall")
        if not fall_frames:
            fall_frames = jump_frames

        self.jump_frames = jump_frames or []
        self.fall_frames = fall_frames or []
        self.frames = self.jump_frames
        self.frame_index = 0

        if isinstance(self.return_state, PlayfulState):
            self.vertical_speed = -15 * 1.5

        self.update_frame()

    def update_animation(self):
        if not self.frames:
            return
        if self.frame_index < len(self.frames) - 1:
            self.frame_index += 1
        else:
            if self.is_falling:
                self.frame_index = len(self.frames) - 1
            else:
                self.frame_index = 0
        self.update_frame()

    def update_position(self):
        self.vertical_speed += 1
        self.duck.duck_y += self.vertical_speed

        if not self.is_falling and self.vertical_speed >= 0:
            self.is_falling = True
            self.frames = self.fall_frames
            self.frame_index = 0

        if self.duck.duck_y + self.duck.duck_height >= self.duck.ground_level:
            self.duck.duck_y = self.duck.ground_level - self.duck.duck_height
            self.vertical_speed = 0
            self.duck.move(int(self.duck.duck_x), int(self.duck.duck_y))
            if self.return_state:
                self.duck.change_state(LandingState(self.duck, next_state=self.return_state))
            else:
                self.duck.change_state(LandingState(self.duck))
        else:
            self.duck.move(int(self.duck.duck_x), int(self.duck.duck_y))

    def exit(self):
        pass

    def update_frame(self):
        if not self.frames:
            return
        frame = self.frames[self.frame_index]
        if not self.duck.facing_right:
            frame = frame.transformed(QtGui.QTransform().scale(-1, 1))
        self.duck.current_frame = frame
        self.duck.update()


class SleepingState(State):
    def enter(self):
        frames = self.duck.resources.get_animation_frames_by_name("sleep")
        if not frames:
            frames = self.duck.resources.get_animation_frames_by_name("idle")
        self.frames = frames or []
        self.frame_index = 0
        self.update_frame()

        self.wake_up_timer = QtCore.QTimer()
        self.wake_up_timer.setSingleShot(True)
        random_interval = random.randint(900000, 3600000)
        self.wake_up_timer.timeout.connect(self.wake_up)
        self.wake_up_timer.start(random_interval)

    def update_animation(self):
        if not self.frames:
            return
        self.frame_index = (self.frame_index + 1) % len(self.frames)
        self.update_frame()

    def update_position(self):
        pass

    def exit(self):
        if hasattr(self, "wake_up_timer") and self.wake_up_timer.isActive():
            self.wake_up_timer.stop()
            self.wake_up_timer = None
            logging.info("SleepingState: Wake up timer stopped.")

    def update_frame(self):
        if not self.frames:
            return
        self.duck.current_frame = self.frames[self.frame_index]
        self.duck.update()

    def handle_mouse_press(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.duck.last_interaction_time = time.time()
            self.duck.change_state(DraggingState(self.duck), event)
        else:
            super().handle_mouse_press(event)

    def wake_up(self):
        logging.info("SleepingState: The wake-up timer has expired, the duck is waking up.")
        self.duck.last_interaction_time = time.time()
        self.duck.change_state(WalkingState(self.duck))


class IdleState(State):
    def __init__(self, duck):
        super().__init__(duck)
        self.start_time = time.time()
        self.cursor_positions = []

    def enter(self):
        idle_animations = self.duck.resources.get_idle_animations()
        if not idle_animations:
            idle_animations = ["idle"]
        selected_idle = random.choice(idle_animations)
        frames = self.duck.resources.get_animation_frames_by_name(selected_idle)
        self.frames = frames or []
        self.frame_index = 0
        self.update_frame()

    def update_animation(self):
        if not self.frames:
            return
        self.frame_index = (self.frame_index + 1) % len(self.frames)
        self.update_frame()

    def update_position(self):
        if self.duck.is_listening:
            return
        elapsed_time = time.time() - self.start_time
        if elapsed_time > self.duck.idle_duration:
            self.duck.change_state(WalkingState(self.duck))

    def exit(self):
        if hasattr(self, "cursor_shake_timer"):
            self.cursor_shake_timer.stop()
            self.cursor_shake_timer = None

    def update_frame(self):
        if not self.frames:
            return
        self.duck.current_frame = self.frames[self.frame_index]
        self.duck.update()


class PlayfulState(State):
    def __init__(self, duck):
        super().__init__(duck)
        self.start_time = time.time()
        self.duration = random.randint(20, 120)
        self.speed_multiplier = 2
        self.has_jumped = False
        self.previous_direction = duck.direction
        self.previous_facing_right = duck.facing_right

    def enter(self):
        self.duck.duck_speed = self.duck.base_duck_speed * self.speed_multiplier * (self.duck.pet_size / 3)
        frames = self.duck.resources.get_animation_frames_by_name("walk")
        if not frames:
            frames = self.duck.resources.get_animation_frames_by_name("idle")
        self.frames = frames or []
        self.frame_index = 0
        self.update_frame()

    def update_animation(self):
        if not self.frames:
            return
        self.frame_index = (self.frame_index + 1) % len(self.frames)
        frame = self.frames[self.frame_index]
        if not self.duck.facing_right:
            frame = frame.transformed(QtGui.QTransform().scale(-1, 1))
        self.duck.current_frame = frame
        self.duck.update()

    def update_position(self):
        current_time = time.time()
        if current_time - self.start_time > self.duration:
            self.duck.change_state(IdleState(self.duck))
            return
        self.chase_cursor()

    def chase_cursor(self):
        cursor_pos = QtGui.QCursor.pos()
        cursor_x = cursor_pos.x()
        duck_center_x = self.duck.duck_x + (self.duck.current_frame.width() if self.duck.current_frame else 64) / 2

        if cursor_x > duck_center_x + 10:
            desired_direction = 1
        elif cursor_x < duck_center_x - 10:
            desired_direction = -1
        else:
            desired_direction = self.duck.direction

        if desired_direction != self.duck.direction:
            self.duck.direction = desired_direction
            self.duck.facing_right = desired_direction == 1

        movement_speed = self.duck.duck_speed
        self.duck.duck_x += desired_direction * movement_speed

        screen = QtWidgets.QApplication.primaryScreen()
        screen_rect = screen.geometry()
        max_x = screen_rect.width() - (self.duck.current_frame.width() if self.duck.current_frame else 64)
        self.duck.duck_x = max(0, min(self.duck.duck_x, max_x))
        self.duck.move(int(self.duck.duck_x), int(self.duck.duck_y))

        distance_x = abs(cursor_x - duck_center_x)
        if distance_x < 50 and not self.has_jumped:
            self.duck.change_state(JumpingState(self.duck, return_state=self))
            self.has_jumped = True
        elif distance_x >= 100:
            self.has_jumped = False

    def exit(self):
        self.duck.playful = False
        self.duck.duck_speed = self.duck.base_duck_speed * (self.duck.pet_size / 3)
        self.duck.animation_timer.setInterval(100)
        self.duck.direction = self.previous_direction
        self.duck.facing_right = self.previous_facing_right
        if isinstance(self.duck.state, WalkingState):
            self.duck.state.frame_index = 0
            self.duck.state.update_frame()
        elif isinstance(self.duck.state, IdleState):
            self.duck.state.frame_index = 0
            self.duck.state.update_frame()

    def handle_mouse_press(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.duck.change_state(DraggingState(self.duck), event)
        else:
            super().handle_mouse_press(event)

    def update_frame(self):
        if self.frames:
            frame = self.frames[self.frame_index]
            if not self.duck.facing_right:
                frame = frame.transformed(QtGui.QTransform().scale(-1, 1))
            self.duck.current_frame = frame
            self.duck.update()
