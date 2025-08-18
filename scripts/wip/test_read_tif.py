import rasterio
import numpy as np
from scipy.interpolate import griddata
from rasterio.warp import reproject, Resampling
from rasterio.enums import Resampling as ResamplingEnum
import rasterio.mask

def read_tif(map1_path):
    """
    Read information of tif file using rasterio.open(file)

    Parameters
    ----------
    map1_path : TYPE
        path to tif file

    Returns
    -------
    
    map1_data : np.Array(float)
        The array of the values contained inside the file. Missing values are
        set at np.nan.
    map1_transform : affine.Affine object
            Affine transformation applied to such data.
    map1_crs : rasterio.crs.CRS object
        Projection system of the data.
    map1_profile : rasterio.profile.Profile object
        Metadata of tif.
    map1_nodata : float
        Original value of missing data.

    """
    # Read the primary high-resolution map
    with rasterio.open(map1_path) as src1:
        map1_data = src1.read(1)
        map1_transform = src1.transform
        map1_crs = src1.crs
        map1_profile = src1.profile
        map1_nodata = src1.nodata
        
    # Handle nodata values - convert to NaN for processing
    if map1_nodata is not None:
        map1_data = map1_data.astype(float)
        map1_data[map1_data == map1_nodata] = np.nan
        
    return(map1_data, map1_transform, map1_crs, map1_profile, map1_nodata)

def fill_bathymetry_gaps(map1_path, map2_path, output_path):
    """
    Fill missing values in high-resolution bathymetry map using interpolated values 
    from a second bathymetry map.
    
    Args:
        map1_path (str): Path to high-resolution bathymetry map (primary)
        map2_path (str): Path to secondary bathymetry map (gap filler)
        output_path (str): Path for output filled map
    """
    
    # Read the primary high-resolution map
    map1_data, map1_transform, map1_crs, map1_profile, map1_nodata = read_tif(map1_path)
        
    # Read the secondary map
    map2_data, map2_transform, map2_crs, map2_profile, map2_nodata = read_tif(map2_path)
    
    print(map1_data)
    print(map2_data)
    
    # Reproject map2 to match map1's grid if needed
    if map1_crs != map2_crs or map1_transform != map2_transform:
        print("Reprojecting secondary map to match primary map...")
        
        # Create empty array with map1 dimensions
        map2_reprojected = np.empty(map1_data.shape, dtype=np.float64)
        
        # Reproject map2 to map1's coordinate system and grid
        reproject(
            source=map2_data,
            destination=map2_reprojected,
            src_transform=map2_transform,
            src_crs=map2_crs,
            dst_transform=map1_transform,
            dst_crs=map1_crs,
            resampling=Resampling.bilinear
        )
        
        map2_data = map2_reprojected
    
    # Find gaps in map1 (NaN values)
    gaps_mask = np.isnan(map1_data)
    
    if not np.any(gaps_mask):
        print("No gaps found in primary map.")
        return map1_data
    
    print(f"Found {np.sum(gaps_mask)} gap pixels to fill...")
    
    # Create filled map starting with map1
    filled_map = map1_data.copy()
    
    # For gap areas, use map2 values where available
    gap_coords = np.where(gaps_mask)
    valid_map2_mask = ~np.isnan(map2_data)
    
    # Direct replacement where map2 has valid data
    direct_fill_mask = gaps_mask & valid_map2_mask
    filled_map[direct_fill_mask] = map2_data[direct_fill_mask]
    
    # For remaining gaps where map2 also has no data, use interpolation
    remaining_gaps = gaps_mask & ~direct_fill_mask
    
    if np.any(remaining_gaps):
        print("Interpolating remaining gaps...")
        
        # Get coordinates of all valid points (from both maps after direct filling)
        valid_mask = ~np.isnan(filled_map)
        valid_coords = np.where(valid_mask)
        valid_values = filled_map[valid_mask]
        
        # Get coordinates of remaining gaps
        gap_coords = np.where(remaining_gaps)
        
        if len(valid_values) > 3:  # Need at least 3 points for interpolation
            # Create coordinate arrays for interpolation
            points = np.column_stack((valid_coords[0], valid_coords[1]))
            xi = np.column_stack((gap_coords[0], gap_coords[1]))
            
            # Interpolate using nearest neighbor (more stable for bathymetry)
            interpolated_values = griddata(
                points, valid_values, xi, method='nearest'
            )
            
            # Fill remaining gaps with interpolated values
            filled_map[remaining_gaps] = interpolated_values
        else:
            print("Not enough valid points for interpolation.")
    
    # Convert back to original data type and handle nodata
    if map1_nodata is not None:
        # Convert NaN back to nodata value
        final_gaps = np.isnan(filled_map)
        filled_map[final_gaps] = map1_nodata
        filled_map = filled_map.astype(map1_profile['dtype'])
    
    # Save the filled map
    with rasterio.open(output_path, 'w', **map1_profile) as dst:
        dst.write(filled_map, 1)
    
    gaps_filled = np.sum(gaps_mask) - np.sum(np.isnan(filled_map))
    print(f"Successfully filled {gaps_filled} gap pixels.")
    print(f"Output saved to: {output_path}")
    
    return filled_map

# Main execution
if __name__ == "__main__":
    # Path to your TIFF files
    map1_path = '/local/home/lsaisset/DATA/CONFIG_DATA/bathy_tif/Litto3D_5m_Rade_EPSG4326_coupe.tif'
    map2_path = '/local/home/lsaisset/DATA/CONFIG_DATA/bathy_tif/MNT_ATL100m_HOMONIM_WGS84_NM_ZNEG_reprojEPSG4326_coupe.tif'
    output_file = "/local/home/lsaisset/DATA/CONFIG_DATA/bathy_tif/filled_bathymetry_map.tif"
    
    try:
        # Fill gaps in bathymetry map
        filled_data = fill_bathymetry_gaps(map1_path, map2_path, output_file)
        print("Gap filling completed successfully!")
        
    except Exception as e:
        print(f"Error processing bathymetry maps: {str(e)}")
        print("Make sure:")
        print("- Both input files exist and are valid GeoTIFF files")
        print("- You have write permissions for the output directory")
        print("- Required Python packages are installed: rasterio, scipy, numpy")
    
    
    
    resu_data, _, _, _, _ = read_tif(output_file)
    
    import matplotlib.pyplot as plt
    
    fig, ax = plt.subplots()
    ax.set_aspect(1)
    ax.pcolor(resu_data[4000:3000:-1, 7500:9500:1])
    plt.show(fig)
    