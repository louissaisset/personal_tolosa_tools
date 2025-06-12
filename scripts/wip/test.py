import rasterio
import numpy as np
from rasterio.transform import from_origin

# Path to your TIFF files
tiff_path_1 = '/local/home/lsaisset/DATA/CONFIG_DATA/bathy_tif/Litto3D_5m_Rade_EPSG4326_coupe.tif'
tiff_path_2 = '/local/home/lsaisset/DATA/CONFIG_DATA/bathy_tif/MNT_ATL100m_HOMONIM_WGS84_NM_ZNEG_reprojEPSG4326_coupe.tif'

# Open the first TIFF file
with rasterio.open(tiff_path_1) as src1:
    # Read the raster data
    raster_data_1 = src1.read(1)  # Reads the first band
    # Get metadata
    metadata_1 = src1.meta
    # Get the coordinate reference system (CRS)
    crs_1 = src1.crs
    # Get the transform
    transform_1 = src1.transform

    # Get the number of rows and columns
    rows, cols = raster_data_1.shape

    # Generate grid cell centers
    x_coords = np.arange(cols) + 0.5
    y_coords = np.arange(rows) + 0.5

    # Convert pixel coordinates to world coordinates
    x_world, y_world = rasterio.transform.xy(transform_1, y_coords[:, np.newaxis], x_coords[np.newaxis, :])

    # Sample the raster data at the grid points
    height_values_1 = raster_data_1[y_coords.astype(int), x_coords.astype(int)]

# Open the second TIFF file
with rasterio.open(tiff_path_2) as src2:
    # Read the raster data
    raster_data_2 = src2.read(1)  # Reads the first band
    # Get the transform
    transform_2 = src2.transform

    # Create a mask for NaN values in the first raster
    nan_mask = np.isnan(height_values_1)

    # Get the indices of NaN values
    nan_indices = np.where(nan_mask)

    # Interpolate height values from the second raster for NaN cells in the first raster
    for i, j in zip(nan_indices[0], nan_indices[1]):
        # Convert pixel coordinates to world coordinates for the NaN cell
        x, y = rasterio.transform.xy(transform_1, i, j)

        # Convert world coordinates to pixel coordinates in the second raster
        row, col = ~transform_2 * (x, y)

        # Sample the height value from the second raster
        height_values_1[i, j] = raster_data_2[int(row), int(col)]

# Combine x, y coordinates and height values into a list of points
grid_points_with_height = [{"x": x, "y": y, "height": height}
                           for x, y, height in zip(x_world.flatten(), y_world.flatten(), height_values_1.flatten())]

print("Number of grid points with height values:", len(grid_points_with_height))
print("First few grid points with height values:", grid_points_with_height[:5])

# Now you have a list of grid points with their corresponding height values, including interpolated values for NaN cells