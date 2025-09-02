# import xarray as xr
# import numpy as np
# import matplotlib.pyplot as plt

# # file = "/local/home/lsaisset/DATA/CONFIG_DATA/grib/ATL/vent_arpege_anaMAN.20090121-26.ATL.grb"
# file = "/local/home/lsaisset/DATA/CONFIG_DATA/grib/ATL/pmer_u10_v10_20210401_20240930_corrected.grib"

# A = xr.open_dataset(file, engine='cfgrib')

# B = A.where(np.logical_and(np.logical_and(A.latitude>=47.8, 
#                                           A.latitude<=48.5),  
#                            np.logical_and(A.longitude>=-5.5, 
#                                           A.longitude<=-4)))




# import pygrib

# input_file = "/local/home/lsaisset/DATA/CONFIG_DATA/grib/ATL/pmer_u10_v10_20210401_20240930_corrected.grib"
# output_file = "/local/home/lsaisset/DATA/CONFIG_DATA/grib/ATL/test.grib"

# # Open the original GRIB file with pygrib
# grbs = pygrib.open(input_file)

# # Create a new GRIB file
# new_grbs = pygrib.open(output_file, 'w')

# # Iterate through the messages in the original GRIB file
# for grb in grbs:
#     # Check if the message is within the desired domain
#     if (grb.latitudes >= 30).any() and (grb.latitudes <= 50).any() and \
#        (grb.longitudes >= -10).any() and (grb.longitudes <= 10).any():
#         # Write the message to the new GRIB file
#         new_grbs.write(grb)

# # Close the GRIB files
# grbs.close()
# new_grbs.close()

import pygrib
import numpy as np

def extract_grib_subdomain(input_grib, output_grib, min_latitude, max_latitude, 
                          min_longitude, max_longitude):
    """
    Extract a subdomain from a GRIB file and save to a new GRIB file.
    
    Parameters:
    -----------
    input_grib : str
        Path to input GRIB file
    output_grib : str  
        Path to output GRIB file
    min_latitude : float
        Minimum latitude of subdomain
    max_latitude : float
        Maximum latitude of subdomain
    min_longitude : float
        Minimum longitude of subdomain (can be negative)
    max_longitude : float
        Maximum longitude of subdomain (can be negative)
    """
    
    # Open input GRIB file
    grbs = pygrib.open(input_grib)
    
    # Create output GRIB file
    with open(output_grib, 'wb') as output_file:
        
        # Process each message in the GRIB file
        for grb in grbs:
            try:
                # Get lat/lon arrays for current message
                lats, lons = grb.latlons()
                
                # Handle longitude wrapping (convert to 0-360 or -180-180 as needed)
                if min_longitude < 0 or max_longitude < 0:
                    # Working with -180 to 180 range
                    lons = np.where(lons > 180, lons - 360, lons)
                
                # Create mask for subdomain
                lat_mask = (lats >= min_latitude) & (lats <= max_latitude)
                lon_mask = (lons >= min_longitude) & (lons <= max_longitude)
                subdomain_mask = lat_mask & lon_mask
                
                # Check if subdomain contains any data points
                if not np.any(subdomain_mask):
                    print(f"Warning: No data points found in subdomain for message {grb.messagenumber}")
                    continue
                
                # Get data values
                data = grb.values
                
                # Find bounding box indices for efficient extraction
                lat_indices = np.where(np.any(subdomain_mask, axis=1))[0]
                lon_indices = np.where(np.any(subdomain_mask, axis=0))[0]
                
                if len(lat_indices) == 0 or len(lon_indices) == 0:
                    continue
                    
                min_lat_idx, max_lat_idx = lat_indices[0], lat_indices[-1]
                min_lon_idx, max_lon_idx = lon_indices[0], lon_indices[-1]
                
                # Extract subdomain
                sub_data = data[min_lat_idx:max_lat_idx+1, min_lon_idx:max_lon_idx+1]
                sub_lats = lats[min_lat_idx:max_lat_idx+1, min_lon_idx:max_lon_idx+1]
                sub_lons = lons[min_lat_idx:max_lat_idx+1, min_lon_idx:max_lon_idx+1]
                
                # Create new GRIB message with subdomain data
                # Copy original message attributes
                new_grb = grb.clone()
                
                # Update grid dimensions
                new_grb['Ni'] = sub_data.shape[1]  # Number of points along longitude
                new_grb['Nj'] = sub_data.shape[0]  # Number of points along latitude
                
                # Update geographic bounds
                new_grb['latitudeOfFirstGridPointInDegrees'] = float(sub_lats[0, 0])
                new_grb['latitudeOfLastGridPointInDegrees'] = float(sub_lats[-1, -1])
                new_grb['longitudeOfFirstGridPointInDegrees'] = float(sub_lons[0, 0])
                new_grb['longitudeOfLastGridPointInDegrees'] = float(sub_lons[-1, -1])
                
                # Set the data values
                new_grb.values = sub_data
                
                # Write to output file
                output_file.write(new_grb.tostring())
                
                print(f"Processed message {grb.messagenumber}: {grb.name} - {grb.typeOfLevel} {grb.level}")
                
            except Exception as e:
                print(f"Error processing message {grb.messagenumber}: {str(e)}")
                continue
    
    grbs.close()
    print(f"Subdomain extraction complete. Output saved to: {output_grib}")


def extract_grib_subdomain_alternative(input_grib, output_grib, min_latitude, max_latitude,
                                     min_longitude, max_longitude):
    """
    Alternative method using data() method with lat/lon bounds - more efficient for large files
    """
    grbs = pygrib.open(input_grib)
    
    with open(output_grib, 'wb') as output_file:
        for grb in grbs:
            # try:
            # Extract data directly within lat/lon bounds
            data, lats, lons = grb.data(lat1=min_latitude, lat2=max_latitude,
                                        lon1=min_longitude, lon2=max_longitude)
        
            if data.size == 0:
                print(f"No data in subdomain for message {grb.messagenumber}")
                continue
            
            # Clone and modify the GRIB message
            new_grb = grb.clone()
            new_grb['Ni'] = data.shape[1]
            print(0)
            new_grb['Nj'] = data.shape[0]
            print(1)
            new_grb['latitudeOfFirstGridPointInDegrees'] = float(lats[0, 0])
            print(2)
            new_grb['latitudeOfLastGridPointInDegrees'] = float(lats[-1, -1])
            print(3)
            new_grb['longitudeOfFirstGridPointInDegrees'] = float(lons[0, 0])
            print(4)
            new_grb['longitudeOfLastGridPointInDegrees'] = float(lons[-1, -1])
            print(5)
            new_grb.values = data
            
            output_file.write(new_grb.tostring())
            print(f"Processed: {grb.name} - Level: {grb.level}")
        
            # except Exception as e:
            #     print(f"Error with message {grb.messagenumber}: {str(e)}")
            #     continue
    
    grbs.close()
    print(f"Alternative extraction complete. Output: {output_grib}")



def extract_grib_subdomain_eccodes(input_grib, output_grib, min_latitude, max_latitude,
                                  min_longitude, max_longitude):
    """
    Alternative using eccodes directly (more reliable)
    Requires: pip install eccodes-python
    """
    try:
        from eccodes import codes_grib_new_from_file, codes_get, codes_get_array
        from eccodes import codes_set, codes_clone, codes_set_array, codes_release, codes_write
        
        with open(input_grib, 'rb') as input_file:
            with open(output_grib, 'wb') as output_file:
                
                while True:
                    # Get next message
                    gid = codes_grib_new_from_file(input_file)
                    if gid is None:
                        break
                    
                    try:
                        # Get original grid info
                        ni = codes_get(gid, 'Ni')
                        nj = codes_get(gid, 'Nj')
                        
                        # Get all lat/lon values
                        lats = codes_get_array(gid, 'latitudes')
                        lons = codes_get_array(gid, 'longitudes')
                        values = codes_get_array(gid, 'values')
                        
                        # Reshape to 2D if needed
                        if len(lats.shape) == 1:
                            lats = lats.reshape(nj, ni)
                            lons = lons.reshape(nj, ni)
                            values = values.reshape(nj, ni)
                        
                        # Create masks for subdomain
                        lat_mask = (lats >= min_latitude) & (lats <= max_latitude)
                        lon_mask = (lons >= min_longitude) & (lons <= max_longitude)
                        subdomain_mask = lat_mask & lon_mask
                        
                        if not np.any(subdomain_mask):
                            print(f"No data in subdomain for current message")
                            continue
                        
                        # Find bounding box
                        rows, cols = np.where(subdomain_mask)
                        min_row, max_row = rows.min(), rows.max()
                        min_col, max_col = cols.min(), cols.max()
                        
                        # Extract subdomain
                        sub_values = values[min_row:max_row+1, min_col:max_col+1]
                        sub_lats = lats[min_row:max_row+1, min_col:max_col+1]
                        sub_lons = lons[min_row:max_row+1, min_col:max_col+1]
                        
                        # Create new message
                        new_gid = codes_clone(gid)
                        
                        # Update grid parameters
                        codes_set(new_gid, 'Ni', sub_values.shape[1])
                        codes_set(new_gid, 'Nj', sub_values.shape[0])
                        codes_set(new_gid, 'latitudeOfFirstGridPointInDegrees', float(sub_lats[0, 0]))
                        codes_set(new_gid, 'latitudeOfLastGridPointInDegrees', float(sub_lats[-1, -1]))
                        codes_set(new_gid, 'longitudeOfFirstGridPointInDegrees', float(sub_lons[0, 0]))
                        codes_set(new_gid, 'longitudeOfLastGridPointInDegrees', float(sub_lons[-1, -1]))
                        
                        # Set values
                        codes_set_array(new_gid, 'values', sub_values.flatten())
                        
                        # Write to output
                        codes_write(new_gid, output_file)
                        codes_release(new_gid)
                        
                        param_name = codes_get(gid, 'name', 'Unknown')
                        level = codes_get(gid, 'level', 'Unknown')
                        print(f"Processed: {param_name} - Level: {level}")
                        
                    except Exception as e:
                        print(f"Error processing message: {str(e)}")
                    finally:
                        codes_release(gid)
        
        print(f"ECCODES extraction complete. Output: {output_grib}")
        
    except ImportError:
        print("eccodes-python not available. Install with: pip install eccodes-python")
        print("Falling back to basic pygrib method...")
        extract_grib_subdomain_alternative(input_grib, output_grib, min_latitude, max_latitude,
                                         min_longitude, max_longitude)

# Example usage
if __name__ == "__main__":
    
    # Define your parameters
    input_grib = "/local/home/lsaisset/DATA/CONFIG_DATA/grib/ATL/pmer_u10_v10_20210401_20240930_corrected.grib"
    input_grib = "/local/home/lsaisset/DATA/CONFIG_DATA/grib/ATL/vent_arpege_anaMAN.20090121-26.ATL.grb"
    output_grib = "/local/home/lsaisset/DATA/CONFIG_DATA/grib/ATL/test.grib"
    
    # Define subdomain bounds (example: Western Europe)
    min_latitude = 40.0
    max_latitude = 60.0
    min_longitude = -10.0
    max_longitude = 20.0
    
    
    # # Method 1: Enhanced pygrib approach (avoids clone issues)
    # extract_grib_subdomain_alternative(input_grib, output_grib, min_latitude, max_latitude,
    #                                  min_longitude, max_longitude)
    
    # # Method 1: Full control approach
    # # extract_grib_subdomain(input_grib, output_grib, min_latitude, max_latitude,
    # #                       min_longitude, max_longitude)
    
    # # Method 2: Alternative using built-in data() method (often more efficient)
    # extract_grib_subdomain_alternative(input_grib, output_grib, 
    #                                   min_latitude, max_latitude,
    #                                   min_longitude, max_longitude)

    # extract_grib_subdomain_eccodes(input_grib, output_grib, min_latitude, max_latitude,
    #                                min_longitude, max_longitude)

    import xarray as xr
    from cfgrib.xarray_to_grib import to_grib
    A = xr.open_dataset(input_grib, engine='cfgrib')
    
    to_grib(A, output_grib, grib_keys={'msl':A.msl, 'u':A.u10, 'v':A.v10})
    to_grib(A, output_grib)
    
    B = xr.open_dataset(output_grib, engine='cfgrib')
    
    
    
    import xarray as xr
    from cfgrib.xarray_to_grib import to_grib
    
    # Define your parameters
    # input_grib = "/local/home/lsaisset/DATA/CONFIG_DATA/grib/ATL/pmer_u10_v10_20210401_20240930_corrected.grib"
    input_grib = "/local/home/lsaisset/DATA/CONFIG_DATA/grib/ATL/vent_arpege_anaMAN.20090121-26.ATL.grb"
    output_grib = "/local/home/lsaisset/DATA/CONFIG_DATA/grib/ATL/test.grib"
    
    A = xr.open_dataset(input_grib, engine='cfgrib')
    
    to_grib(A, output_grib, grib_keys={'msl':A.msl, 'u':A.u10, 'v':A.v10})
    to_grib(A, output_grib)
    
    B = xr.open_dataset(output_grib, engine='cfgrib')
    
    
