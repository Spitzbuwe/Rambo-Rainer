"""
Desktop Control Light - Sichere Desktop-Steuerung für Rambo-Rainer
Nur erlaubte Aktionen, alles geloggt, alles validiert.
"""

import subprocess
import time
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum
import json

# Try to import Windows-specific libraries
try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
    # Safety settings
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.1
except ImportError:
    PYAUTOGUI_AVAILABLE = False

try:
    import pygetwindow as gw
    PYGETWINDOW_AVAILABLE = True
except ImportError:
    PYGETWINDOW_AVAILABLE = False

try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False


class DesktopAction(Enum):
    """Erlaubte Desktop-Aktionen"""
    OPEN_PROGRAM = "open_program"
    LIST_WINDOWS = "list_windows"
    FOCUS_WINDOW = "focus_window"
    TYPE_TEXT = "type_text"
    SEND_HOTKEY = "send_hotkey"
    CLICK_TARGET = "click_target"


class DesktopError(Enum):
    """Desktop Control Fehler"""
    PROGRAM_NOT_ALLOWED = "program_not_allowed"
    HOTKEY_NOT_ALLOWED = "hotkey_not_allowed"
    TARGET_NOT_FOUND = "target_not_found"
    WINDOW_NOT_FOUND = "window_not_found"
    LIBRARY_MISSING = "library_missing"
    ACTION_FAILED = "action_failed"
    FEATURE_DISABLED = "feature_disabled"


@dataclass
class DesktopConfig:
    """Desktop Control Konfiguration"""
    allowed_programs: List[str]
    allowed_hotkeys: List[str]
    named_click_targets: Dict[str, Dict[str, Any]]
    feature_flags: Dict[str, bool]
    
    @classmethod
    def default(cls) -> 'DesktopConfig':
        return cls(
            allowed_programs=[
                "notepad.exe",
                "calc.exe",
                "explorer.exe",
                "mspaint.exe",
                "cmd.exe",
                "powershell.exe"
            ],
            allowed_hotkeys=[
                "enter",
                "esc",
                "tab",
                "up",
                "down",
                "left",
                "right",
                "ctrl+s",
                "ctrl+c",
                "ctrl+v",
                "ctrl+a",
                "ctrl+z",
                "ctrl+x",
                "ctrl+f",
                "alt+f4",
                "f5",
                "delete"
            ],
            named_click_targets={
                "notepad_text_area": {
                    "description": "Notepad text input area",
                    "program": "notepad.exe",
                    "x_offset": 50,
                    "y_offset": 50
                },
                "notepad_menu_file": {
                    "description": "Notepad File menu",
                    "program": "notepad.exe",
                    "x_offset": 10,
                    "y_offset": 10
                }
            },
            feature_flags={
                "allow_clicks": True,
                "allow_typing": True,
                "allow_program_launch": True,
                "enabled": True
            }
        )
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'DesktopConfig':
        return cls(**data)


class DesktopController:
    """
    Sicherer Desktop Controller mit Whitelist-Validierung
    """
    
    def __init__(self, config: Optional[DesktopConfig] = None):
        self.config = config or DesktopConfig.default()
        self.action_log: List[Dict] = []
        
        # Check library availability
        self.libraries_available = {
            'pyautogui': PYAUTOGUI_AVAILABLE,
            'pygetwindow': PYGETWINDOW_AVAILABLE,
            'keyboard': KEYBOARD_AVAILABLE
        }
    
    def is_enabled(self) -> bool:
        """Check if desktop control is enabled"""
        return self.config.feature_flags.get('enabled', True)
    
    def validate_program(self, program_name: str) -> Tuple[bool, Optional[str]]:
        """Validiere ob Programm erlaubt ist"""
        if not self.config.feature_flags.get('allow_program_launch', True):
            return False, DesktopError.FEATURE_DISABLED.value
        
        # Normalize program name
        program_lower = program_name.lower()
        if not program_lower.endswith('.exe'):
            program_lower += '.exe'
        
        # Check whitelist
        allowed_lower = [p.lower() for p in self.config.allowed_programs]
        if program_lower not in allowed_lower:
            return False, DesktopError.PROGRAM_NOT_ALLOWED.value
        
        return True, None
    
    def validate_hotkey(self, hotkey: str) -> Tuple[bool, Optional[str]]:
        """Validiere ob Hotkey erlaubt ist"""
        hotkey_lower = hotkey.lower().replace(' ', '')
        allowed_normalized = [h.lower().replace(' ', '') for h in self.config.allowed_hotkeys]
        
        if hotkey_lower not in allowed_normalized:
            return False, DesktopError.HOTKEY_NOT_ALLOWED.value
        
        return True, None
    
    def validate_click_target(self, target_name: str) -> Tuple[bool, Optional[Dict]]:
        """Validiere und liefere Klickziel-Konfiguration"""
        if not self.config.feature_flags.get('allow_clicks', True):
            return False, None
        
        target = self.config.named_click_targets.get(target_name)
        if not target:
            return False, None
        
        return True, target
    
    def log_action(self, action: str, status: str, details: Dict = None, error: str = None):
        """Logge jede Aktion"""
        log_entry = {
            'timestamp': time.time(),
            'action': action,
            'status': status,
            'details': details or {},
            'error': error,
            'libraries': self.libraries_available.copy()
        }
        self.action_log.append(log_entry)
        # Keep last 100 entries
        if len(self.action_log) > 100:
            self.action_log = self.action_log[-100:]
    
    def open_program(self, program_name: str) -> Dict:
        """Starte erlaubtes Programm"""
        # Validate
        is_valid, error = self.validate_program(program_name)
        if not is_valid:
            self.log_action('open_program', 'rejected', {'program': program_name}, error)
            return {
                'success': False,
                'error': error,
                'message': f'Programm "{program_name}" ist nicht erlaubt'
            }
        
        try:
            # Normalize and start
            if not program_name.lower().endswith('.exe'):
                program_name += '.exe'
            
            # Use start command for non-blocking execution
            subprocess.Popen(
                ['start', '', program_name],
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            self.log_action('open_program', 'success', {'program': program_name})
            
            # Wait briefly for window to appear
            time.sleep(0.5)
            
            return {
                'success': True,
                'program': program_name,
                'message': f'{program_name} gestartet'
            }
            
        except Exception as e:
            error_msg = str(e)
            self.log_action('open_program', 'failed', {'program': program_name}, error_msg)
            return {
                'success': False,
                'error': DesktopError.ACTION_FAILED.value,
                'message': f'Fehler beim Starten: {error_msg}'
            }
    
    def list_windows(self) -> Dict:
        """Liste alle Fenster"""
        if not PYGETWINDOW_AVAILABLE:
            self.log_action('list_windows', 'failed', {}, 'pygetwindow nicht verfügbar')
            return {
                'success': False,
                'error': DesktopError.LIBRARY_MISSING.value,
                'message': 'Fenster-API nicht verfügbar (pygetwindow fehlt)'
            }
        
        try:
            windows = gw.getAllWindows()
            window_list = []
            
            for win in windows:
                if win.title and len(win.title.strip()) > 0:
                    window_list.append({
                        'title': win.title,
                        'left': win.left,
                        'top': win.top,
                        'width': win.width,
                        'height': win.height,
                        'isActive': win.isActive
                    })
            
            self.log_action('list_windows', 'success', {'count': len(window_list)})
            
            return {
                'success': True,
                'windows': window_list,
                'count': len(window_list)
            }
            
        except Exception as e:
            error_msg = str(e)
            self.log_action('list_windows', 'failed', {}, error_msg)
            return {
                'success': False,
                'error': DesktopError.ACTION_FAILED.value,
                'message': f'Fehler beim Abrufen: {error_msg}'
            }
    
    def find_window(self, title_pattern: str) -> Optional[Dict]:
        """Finde Fenster nach Titel (partial match)"""
        if not PYGETWINDOW_AVAILABLE:
            return None
        
        try:
            windows = gw.getAllWindows()
            pattern_lower = title_pattern.lower()
            
            for win in windows:
                if win.title and pattern_lower in win.title.lower():
                    return {
                        'title': win.title,
                        'left': win.left,
                        'top': win.top,
                        'width': win.width,
                        'height': win.height,
                        'isActive': win.isActive
                    }
            
            return None
            
        except Exception:
            return None
    
    def focus_window(self, title_pattern: str) -> Dict:
        """Fokussiere Fenster nach Titel"""
        if not PYGETWINDOW_AVAILABLE:
            self.log_action('focus_window', 'failed', {'title': title_pattern}, 'pygetwindow nicht verfügbar')
            return {
                'success': False,
                'error': DesktopError.LIBRARY_MISSING.value,
                'message': 'Fenster-API nicht verfügbar'
            }
        
        try:
            # Find window
            windows = gw.getAllWindows()
            pattern_lower = title_pattern.lower()
            target_window = None
            
            for win in windows:
                if win.title and pattern_lower in win.title.lower():
                    target_window = win
                    break
            
            if not target_window:
                self.log_action('focus_window', 'failed', {'title': title_pattern}, 'window not found')
                return {
                    'success': False,
                    'error': DesktopError.WINDOW_NOT_FOUND.value,
                    'message': f'Fenster mit Titel "{title_pattern}" nicht gefunden'
                }
            
            # Activate window
            try:
                if target_window.isMinimized:
                    target_window.restore()
                target_window.activate()
                time.sleep(0.2)
            except Exception as e:
                # Some windows can't be activated, try alternative
                pass
            
            self.log_action('focus_window', 'success', {'title': target_window.title})
            
            return {
                'success': True,
                'window_title': target_window.title,
                'message': f'Fenster "{target_window.title}" fokussiert'
            }
            
        except Exception as e:
            error_msg = str(e)
            self.log_action('focus_window', 'failed', {'title': title_pattern}, error_msg)
            return {
                'success': False,
                'error': DesktopError.ACTION_FAILED.value,
                'message': f'Fehler beim Fokussieren: {error_msg}'
            }
    
    def type_text(self, text: str, interval: float = 0.01) -> Dict:
        """Tippe Text sicher"""
        if not self.config.feature_flags.get('allow_typing', True):
            self.log_action('type_text', 'rejected', {}, 'typing disabled')
            return {
                'success': False,
                'error': DesktopError.FEATURE_DISABLED.value,
                'message': 'Texteingabe ist deaktiviert'
            }
        
        if not PYAUTOGUI_AVAILABLE:
            self.log_action('type_text', 'failed', {}, 'pyautogui nicht verfügbar')
            return {
                'success': False,
                'error': DesktopError.LIBRARY_MISSING.value,
                'message': 'Texteingabe-API nicht verfügbar (pyautogui fehlt)'
            }
        
        try:
            # Sanitize text - no control characters except common ones
            allowed_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 äöüÄÖÜß!"§$%&/()=?[]{}\|~@#*^°+-.,;:\'-_<> ')
            safe_text = ''.join(c for c in text if c in allowed_chars)
            
            if len(safe_text) > 1000:
                safe_text = safe_text[:1000]
            
            pyautogui.typewrite(safe_text, interval=interval)
            
            self.log_action('type_text', 'success', {'length': len(safe_text)})
            
            return {
                'success': True,
                'text_length': len(safe_text),
                'message': f'Text eingegeben ({len(safe_text)} Zeichen)'
            }
            
        except Exception as e:
            error_msg = str(e)
            self.log_action('type_text', 'failed', {}, error_msg)
            return {
                'success': False,
                'error': DesktopError.ACTION_FAILED.value,
                'message': f'Fehler bei Texteingabe: {error_msg}'
            }
    
    def send_hotkey(self, hotkey: str) -> Dict:
        """Sende erlaubten Hotkey"""
        # Validate
        is_valid, error = self.validate_hotkey(hotkey)
        if not is_valid:
            self.log_action('send_hotkey', 'rejected', {'hotkey': hotkey}, error)
            return {
                'success': False,
                'error': error,
                'message': f'Hotkey "{hotkey}" ist nicht erlaubt'
            }
        
        if not PYAUTOGUI_AVAILABLE and not KEYBOARD_AVAILABLE:
            self.log_action('send_hotkey', 'failed', {'hotkey': hotkey}, 'libraries not available')
            return {
                'success': False,
                'error': DesktopError.LIBRARY_MISSING.value,
                'message': 'Tastatur-API nicht verfügbar'
            }
        
        try:
            # Parse hotkey
            hotkey_clean = hotkey.lower().replace(' ', '').replace('+', ' ')
            keys = hotkey_clean.split()
            
            if len(keys) == 1:
                # Single key
                if KEYBOARD_AVAILABLE:
                    keyboard.send(keys[0])
                else:
                    pyautogui.press(keys[0])
            else:
                # Combination
                if PYAUTOGUI_AVAILABLE:
                    pyautogui.hotkey(*keys)
                elif KEYBOARD_AVAILABLE:
                    # Build keyboard combination
                    combo = '+'.join(keys)
                    keyboard.send(combo)
            
            self.log_action('send_hotkey', 'success', {'hotkey': hotkey})
            
            return {
                'success': True,
                'hotkey': hotkey,
                'message': f'Hotkey {hotkey} gesendet'
            }
            
        except Exception as e:
            error_msg = str(e)
            self.log_action('send_hotkey', 'failed', {'hotkey': hotkey}, error_msg)
            return {
                'success': False,
                'error': DesktopError.ACTION_FAILED.value,
                'message': f'Fehler beim Senden: {error_msg}'
            }
    
    def click_named_target(self, target_name: str) -> Dict:
        """Klicke auf vordefiniertes Ziel"""
        # Validate
        is_valid, target_config = self.validate_click_target(target_name)
        if not is_valid:
            self.log_action('click_target', 'rejected', {'target': target_name}, 'target not configured')
            return {
                'success': False,
                'error': DesktopError.TARGET_NOT_FOUND.value,
                'message': f'Klickziel "{target_name}" ist nicht konfiguriert'
            }
        
        if not PYAUTOGUI_AVAILABLE:
            self.log_action('click_target', 'failed', {'target': target_name}, 'pyautogui not available')
            return {
                'success': False,
                'error': DesktopError.LIBRARY_MISSING.value,
                'message': 'Maus-API nicht verfügbar'
            }
        
        try:
            # Find associated program window
            program = target_config.get('program', '')
            if program:
                windows = gw.getAllWindows() if PYGETWINDOW_AVAILABLE else []
                target_window = None
                
                for win in windows:
                    if win.title and program.replace('.exe', '').lower() in win.title.lower():
                        target_window = win
                        break
                
                if target_window:
                    # Click relative to window
                    x = target_window.left + target_config.get('x_offset', 0)
                    y = target_window.top + target_config.get('y_offset', 0)
                else:
                    # Window not found, use screen center with offset
                    screen_width, screen_height = pyautogui.size()
                    x = screen_width // 2 + target_config.get('x_offset', 0)
                    y = screen_height // 2 + target_config.get('y_offset', 0)
            else:
                # No program associated, use screen center
                screen_width, screen_height = pyautogui.size()
                x = screen_width // 2 + target_config.get('x_offset', 0)
                y = screen_height // 2 + target_config.get('y_offset', 0)
            
            # Safety bounds check
            screen_width, screen_height = pyautogui.size()
            x = max(0, min(x, screen_width - 1))
            y = max(0, min(y, screen_height - 1))
            
            # Perform click
            pyautogui.click(x, y)
            
            self.log_action('click_target', 'success', {
                'target': target_name,
                'x': x,
                'y': y
            })
            
            return {
                'success': True,
                'target': target_name,
                'position': {'x': x, 'y': y},
                'message': f'Klick auf "{target_name}" ausgeführt'
            }
            
        except Exception as e:
            error_msg = str(e)
            self.log_action('click_target', 'failed', {'target': target_name}, error_msg)
            return {
                'success': False,
                'error': DesktopError.ACTION_FAILED.value,
                'message': f'Fehler beim Klicken: {error_msg}'
            }
    
    def get_config(self) -> Dict:
        """Liefere aktuelle Konfiguration"""
        return {
            'config': self.config.to_dict(),
            'libraries': self.libraries_available,
            'enabled': self.is_enabled()
        }
    
    def get_action_log(self, limit: int = 50) -> List[Dict]:
        """Liefere Aktions-Log"""
        return self.action_log[-limit:]


# Global controller instance
desktop_controller = DesktopController()


def execute_desktop_action(action_type: str, params: Dict, task_id: str = None) -> Dict:
    """
    Führe Desktop-Aktion aus mit Task-Integration
    """
    controller = desktop_controller
    
    if not controller.is_enabled():
        return {
            'success': False,
            'error': 'desktop_control_disabled',
            'message': 'Desktop Control ist deaktiviert'
        }
    
    result = {'success': False, 'action': action_type}
    
    try:
        if action_type == 'open_program':
            result = controller.open_program(params.get('program', ''))
        
        elif action_type == 'list_windows':
            result = controller.list_windows()
        
        elif action_type == 'focus_window':
            result = controller.focus_window(params.get('title', ''))
        
        elif action_type == 'type_text':
            result = controller.type_text(params.get('text', ''))
        
        elif action_type == 'send_hotkey':
            result = controller.send_hotkey(params.get('hotkey', ''))
        
        elif action_type == 'click_target':
            result = controller.click_named_target(params.get('target', ''))
        
        else:
            result = {
                'success': False,
                'error': 'unknown_action',
                'message': f'Aktion "{action_type}" ist nicht bekannt'
            }
    
    except Exception as e:
        result = {
            'success': False,
            'error': 'exception',
            'message': str(e)
        }
    
    # Add task context if provided
    if task_id:
        result['task_id'] = task_id
    
    return result


# Installationscheck
def check_libraries() -> Dict:
    """Prüfe welche Bibliotheken verfügbar sind"""
    return {
        'pyautogui': PYAUTOGUI_AVAILABLE,
        'pygetwindow': PYGETWINDOW_AVAILABLE,
        'keyboard': KEYBOARD_AVAILABLE,
        'all_available': PYAUTOGUI_AVAILABLE and PYGETWINDOW_AVAILABLE and KEYBOARD_AVAILABLE,
        'install_command': 'pip install pyautogui pygetwindow keyboard'
    }
