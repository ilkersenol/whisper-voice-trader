#!/usr/bin/env python3
"""
UI Compiler Script
Compiles all .ui files to Python using pyuic5
"""
import os
import subprocess
from pathlib import Path

def compile_ui_files():
    """Compile all .ui files in ui/raw/ to ui/generated/"""
    
    # Paths
    raw_dir = Path(__file__).parent.parent / "ui" / "raw"
    generated_dir = Path(__file__).parent.parent / "ui" / "generated"
    
    # Create generated directory
    generated_dir.mkdir(exist_ok=True)
    
    # Create __init__.py in generated
    (generated_dir / "__init__.py").touch()
    
    # Get all .ui files
    ui_files = list(raw_dir.glob("*.ui"))
    
    if not ui_files:
        print("❌ No .ui files found in ui/raw/")
        return
    
    print(f"🔄 Compiling {len(ui_files)} UI files...\n")
    
    compiled_count = 0
    for ui_file in ui_files:
        # Output filename: main_window.ui -> ui_main_window.py
        output_name = f"ui_{ui_file.stem}.py"
        output_path = generated_dir / output_name
        
        # Compile command
        cmd = ["pyuic5", "-x", str(ui_file), "-o", str(output_path)]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"✅ {ui_file.name} -> {output_name}")
            compiled_count += 1
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to compile {ui_file.name}")
            print(f"   Error: {e.stderr}")
    
    print(f"\n✅ Successfully compiled {compiled_count}/{len(ui_files)} files")
    print(f"📁 Output directory: {generated_dir}")

if __name__ == "__main__":
    compile_ui_files()
