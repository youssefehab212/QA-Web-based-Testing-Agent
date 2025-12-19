from tools.decorator import tool
from pathlib import Path
import shutil

@tool()
def list_directory_files(path: str = ".", depth: int = 1) -> dict:
    """
    List files and directories in the given path up to a certain depth using pathlib.
    Returns a dictionary with success/error status and result/message.
    """
    try:
        # TODO:
        base = Path(path)
        result = {}

        def list_recursive(current_path, current_depth, max_depth):
            if current_depth > max_depth:
                return {}
            
            items = {}
            for item in sorted(current_path.iterdir()):
                if item.is_dir():
                    items[item.name + "/"] = list_recursive(item, current_depth + 1, max_depth)
                else:
                    items[item.name] = f"{item.stat().st_size} bytes"
            return items
        
        result = list_recursive(base, 1, depth)
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool()
def read_file(file_path: str) -> dict:
    """
    Read the content of a file.
    Returns a dictionary with success/error status and result/message.
    """
    try:
        # TODO:
        p = Path(file_path)
        content = p.read_text()
        return {"success": True, "result": content}
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool()
def write_file(file_path: str, content: str) -> dict:
    """
    Write content to a file.
    Returns a dictionary with success/error status and result/message.
    """
    try:
        # TODO:
        p = Path(file_path)
        p.write_text(content)
        return {"success": True, "result": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool()
def create_folder(folder_path: str) -> dict:
    """
    Create a new folder (directory) at the specified path.
    Returns a dictionary with success/error status and result/message.
    """
    # TODO:
    try:
        p = Path(folder_path)
        p.mkdir(parents=True, exist_ok=False)
        return {"success": True, "result": True}
    except FileExistsError:
        return {"success": False, "error": f"Folder already exists: {folder_path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool()
def remove_folder(folder_path: str) -> dict:
    """
    Remove a folder (directory) and all its contents at the specified path.
    Returns a dictionary with success/error status and result/message.
    """
    try:
        # TODO:
        p = Path(folder_path)
        if not p.is_dir():
            return {"success": False, "error": f"Folder not found: {folder_path}"}
        shutil.rmtree(p)
        return {"success": True, "result": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool()
def remove_file(file_path: str) -> dict:
    """
    Remove a file at the specified path.
    Returns a dictionary with success/error status and result/message.
    """
    try:
        # TODO:
        p = Path(file_path)
        p.unlink()
        return {"success": True, "result": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
