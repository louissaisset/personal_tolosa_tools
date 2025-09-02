#!/usr/bin/env python3
"""
GRIB File Generator with Meteorological Parameter Scaling

This script takes meteorological parameters and creates a new GRIB file
by first creating a unitary GRIB file, then scaling the values using grib_set commands.
"""

import subprocess
import math
import os
import sys
import argparse
from typing import Tuple
from pathlib import Path

def nautical_to_uv_components(wind_intensity: float, wind_direction_nautical: float) -> Tuple[float, float]:
    """
    Convert wind intensity and nautical direction to U and V components.
    
    Args:
        wind_intensity: Wind speed in m/s
        wind_direction_nautical: Wind direction in nautical degrees (0-360)
                                where 0° is North, 90° is East
    
    Returns:
        Tuple of (u_component, v_component) in m/s
        
    Note:
        - U component: positive eastward
        - V component: positive northward
        - Nautical direction is "wind coming from" direction
    """
    # Convert nautical degrees to radians
    # Nautical direction is "coming from", so we add 180° to get "going to"
    direction_rad = math.radians((wind_direction_nautical + 180) % 360)
    
    # Calculate components
    u_component = wind_intensity * math.sin(direction_rad)
    v_component = wind_intensity * math.cos(direction_rad)
    
    return u_component, v_component

def run_grib_command(cmd_args: list, description: str) -> bool:
    """
    Execute a grib command with error handling.
    
    Args:
        cmd_args: List of command arguments
        description: Description of the operation for logging
        
    Returns:
        True if command executed successfully, False otherwise
    """
    try:
        print(f"Executing: {' '.join(cmd_args)}")
        result = subprocess.run(cmd_args, check=True, capture_output=True, text=True)
        print(f"✅ Successfully {description}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error {description}: {e}")
        if e.stdout:
            print(f"Command output: {e.stdout}")
        if e.stderr:
            print(f"Command error: {e.stderr}")
        return False
    except FileNotFoundError:
        print("❌ Error: grib_set command not found. Please ensure ECMWF grib_api or eccodes is installed.")
        return False

def create_unitary_grib(input_file: str, unitary_file: str) -> bool:
    """
    Create a unitary GRIB file by first zeroing out values then adding 1.
    
    Args:
        input_file: Path to input GRIB file
        unitary_file: Path to output unitary GRIB file
        
    Returns:
        True if successful, False otherwise
    """
    zeroed_file = f"{unitary_file}.zeroed_tmp"
    
    try:
        # Step 1: Zero out all values
        cmd_zero = ['grib_set', '-s', 'scaleValuesBy=0', input_file, zeroed_file]
        success = run_grib_command(cmd_zero, "zeroed out GRIB values")
        if not success:
            return False
        
        # Step 2: Add 1 to all values (making them unitary)
        cmd_unity = ['grib_set', '-s', 'offsetValuesBy=1', zeroed_file, unitary_file]
        success = run_grib_command(cmd_unity, "created unitary GRIB file")
        if not success:
            return False
            
        return True
        
    finally:
        # Clean up temporary zeroed file
        if os.path.exists(zeroed_file):
            os.remove(zeroed_file)
            print(f"🗑️  Cleaned up temporary file: {zeroed_file}")

def scale_grib_variable(input_file: str, output_file: str, cf_var_name: str, scale_value: float) -> bool:
    """
    Scale a specific variable in a GRIB file.
    
    Args:
        input_file: Input GRIB file path
        output_file: Output GRIB file path
        cf_var_name: CF variable name (msl, u10, v10)
        scale_value: Scaling factor
        
    Returns:
        True if command executed successfully, False otherwise
    """
    cmd = [
        'grib_set',
        '-w', f'cfVarName={cf_var_name}',
        '-s', f'scaleValuesBy={scale_value}',
        input_file,
        output_file
    ]
    
    return run_grib_command(cmd, f"scaled {cf_var_name} variable")

def create_synthetic_grib_file(
    input_file: str,
    output_file: str,
    new_pressure: float,
    new_wind_intensity: float,
    new_wind_direction_nautical: float
) -> bool:
    """
    Create a synthetic GRIB file with specified meteorological parameters.
    
    Args:
        input_file: Path to input GRIB file
        output_file: Path to output GRIB file
        new_pressure: New mean sea level pressure value (Pa)
        new_wind_intensity: New wind intensity (m/s)
        new_wind_direction_nautical: Wind direction in nautical degrees
        
    Returns:
        True if successful, False otherwise
    """
    
    # Check if input file exists
    if not os.path.exists(input_file):
        print(f"❌ Error: Input file {input_file} does not exist.")
        return False
    
    # Calculate U and V components from wind intensity and direction
    u_component, v_component = nautical_to_uv_components(new_wind_intensity, new_wind_direction_nautical)
    
    print(f"\n🌤️  Processing meteorological parameters:")
    print(f"  📊 Pressure (MSL): {new_pressure} Pa")
    print(f"  💨 Wind intensity: {new_wind_intensity} m/s")
    print(f"  🧭 Wind direction (nautical): {new_wind_direction_nautical}°")
    print(f"  ➡️  Calculated U-component: {u_component:.3f} m/s")
    print(f"  ⬆️  Calculated V-component: {v_component:.3f} m/s")
    print()
    
    # Define temporary file names
    unitary_file = f"{output_file}.unitary_tmp"
    temp_file1 = f"{output_file}.temp1"
    temp_file2 = f"{output_file}.temp2"
    
    try:
        print("🔄 Step 1: Creating unitary GRIB file...")
        success = create_unitary_grib(input_file, unitary_file)
        if not success:
            return False
        
        print("\n🔄 Step 2: Scaling mean sea level pressure...")
        success = scale_grib_variable(unitary_file, temp_file1, 'msl', new_pressure)
        if not success:
            return False
        
        print("\n🔄 Step 3: Scaling U-component (10m wind)...")
        success = scale_grib_variable(temp_file1, temp_file2, 'u10', u_component)
        if not success:
            return False
        
        print("\n🔄 Step 4: Scaling V-component (10m wind)...")
        success = scale_grib_variable(temp_file2, output_file, 'v10', v_component)
        if not success:
            return False
        
        print(f"\n✅ Successfully created synthetic GRIB file: {output_file}")
        return True
        
    finally:
        # Clean up all temporary files
        temp_files = [unitary_file, temp_file1, temp_file2]
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                os.remove(temp_file)
                print(f"🗑️  Cleaned up temporary file: {temp_file}")

def generate_output_filename(input_file: str, pressure: float, wind_intensity: float, wind_direction: float) -> str:
    """
    Generate output filename based on input file and parameters.
    
    Args:
        input_file: Input file path
        pressure: Pressure value
        wind_intensity: Wind intensity value
        wind_direction: Wind direction value
        
    Returns:
        Generated output filename
    """
    input_path = Path(input_file)
    stem = input_path.stem  # filename without extension
    suffix = input_path.suffix  # file extension
    
    output_name = f"{stem}_synthetic_{pressure}_{wind_intensity}_{wind_direction}{suffix}"
    return output_name

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate synthetic GRIB files with specified meteorological parameters",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s 101325 10.5 270
  %(prog)s 101325 10.5 270 -i weather_data.grib
  %(prog)s 101325 10.5 270 -i weather_data.grib -o custom_output.grib
  
Notes:
  - Pressure should be in Pascals (Pa)
  - Wind intensity should be in meters per second (m/s)
  - Wind direction should be in nautical degrees (0-360°, where 0° is North)
        """
    )
    
    parser.add_argument(
        'pressure',
        type=float,
        help='Mean sea level pressure in Pascals (Pa)'
    )
    
    parser.add_argument(
        'wind_intensity',
        type=float,
        help='Wind intensity in meters per second (m/s)'
    )
    
    parser.add_argument(
        'wind_direction',
        type=float,
        help='Wind direction in nautical degrees (0-360°, 0° = North)'
    )
    
    parser.add_argument(
        '-i', '--input',
        dest='input_file',
        default='pmer_u10_v10_20210401_20240930_corrected.grib',
        help='Input GRIB file (default: %(default)s)'
    )
    
    parser.add_argument(
        '-o', '--output',
        dest='output_file',
        help='Output GRIB file (default: auto-generated based on input file and parameters)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    return parser.parse_args()

def validate_arguments(args):
    """Validate command line arguments."""
    errors = []
    
    if args.pressure <= 0:
        errors.append("Pressure must be positive")
    
    if args.wind_intensity < 0:
        errors.append("Wind intensity must be non-negative")
    
    if not (0 <= args.wind_direction <= 360):
        errors.append("Wind direction must be between 0 and 360 degrees")
    
    if not os.path.exists(args.input_file):
        errors.append(f"Input file does not exist: {args.input_file}")
    
    if errors:
        print("❌ Validation errors:")
        for error in errors:
            print(f"  • {error}")
        sys.exit(1)

def main():
    """Main function to handle command line arguments and execute the scaling."""
    
    args = parse_arguments()
    validate_arguments(args)
    
    # Generate output filename if not provided
    if args.output_file is None:
        args.output_file = generate_output_filename(
            args.input_file,
            args.pressure,
            args.wind_intensity,
            args.wind_direction
        )
    
    print(f"🚀 GRIB Synthetic File Generator")
    print(f"📁 Input file: {args.input_file}")
    print(f"📁 Output file: {args.output_file}")
    
    # Execute the GRIB file creation
    success = create_synthetic_grib_file(
        args.input_file,
        args.output_file,
        args.pressure,
        args.wind_intensity,
        args.wind_direction
    )
    
    if success:
        print(f"\n🎉 Successfully generated synthetic GRIB file: {args.output_file}")
        sys.exit(0)
    else:
        print(f"\n💥 Failed to generate synthetic GRIB file")
        sys.exit(1)

if __name__ == "__main__":
    main()
