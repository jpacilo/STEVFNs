#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Nov  1 16:36:27 2021

@author: aniqahsan
@contributor: Mónica Sagastuy Breña (c) 2024-2025
"""

import os
import numpy as np
import pandas as pd
import cvxpy as cp
from ..Base_Assets import Asset_STEVFNs
from ...Network import Edge_STEVFNs


class RE_WIND_Existing_Asset(Asset_STEVFNs):
    """Class of Renewable Energy Sources """
    asset_name = "RE_WIND_Existing"
    target_node_type = "EL"
    
    source_node_type_2 = "NULL" # For Edge 2, to constrain maximum capacity
    target_node_type_2 = "RE_WIND" # For Edge 2, to constrain maximum capacity
    
    source_node_type_3 = "RE_WIND" # For Edge 3, to constrain minimum capacity
    target_node_type_3 = "NULL" # For Edge 3, to constrain minimum capacity

    period = 1
    transport_time = 0
    target_node_time_2 = 0 # For Edge 2, to constrain maximum capacity
    target_node_time_3 = 0 # For Edge 3, to constrain minimum capacity
    
    @staticmethod
    def cost_fun(flows, params):
        return params["sizing_constant"] @ flows # element wise dot product
    
    @staticmethod
    def conversion_fun_2(flows, params):
        '''Conversion function to limit to maximum capacity vector'''
        return params["maximum_size"] - flows
    
    @staticmethod
    def conversion_fun_3(flows, params):
        '''Conversion function to limit to minimum capacity vector'''
        return flows - params["minimum_size"]

        
    def __init__(self):
        super().__init__()
        # NEW ADDITION: Initialize attributes for multi year modeling
        self.year_change_indices = [0]
        self.power_flows = []
        self.existing_capacity_df = pd.DataFrame()
        # EDITED: Temporary initialization of cost and conversion function parameters,
        # shape defined in structure
        self.cost_fun_params = {"sizing_constant": cp.Parameter(nonneg=True)}
        self.conversion_fun_params_2 = {"maximum_size": cp.Parameter(nonneg=True)}
        self.conversion_fun_params_3 = {"minimum_size": cp.Parameter(nonneg=True)}
        return
    
    def define_structure(self, asset_structure):
        self.asset_structure = asset_structure
        self.source_node_location = "NULL"
        self.target_node_location = asset_structure["Location_1"]
        # Add node locations for edge 2
        self.source_node_location_2 = "NULL"
        self.target_node_location_2 = asset_structure["Location_1"]
        # Add node locations for edge 3, opposite direction
        self.source_node_location_3 = asset_structure["Location_1"]
        self.target_node_location_3 = "NULL"
        
        self.target_node_times = np.arange(asset_structure["Start_Time"], 
                                           asset_structure["End_Time"], 
                                           self.period)
        self.number_of_edges = len(self.target_node_times)
        # Define the number of years in the control horizon
        self.num_years = int(self.network.system_parameters_df.loc["control_horizon", "value"] / 8760)
        self.gen_profile = cp.Parameter(shape = (self.number_of_edges), nonneg=True)
        # EDITED: set size of RE asset as array of sizes per horizon modeled
        self.flows = cp.Variable(shape=(self.num_years,), nonneg=True) # New capacities to install per year
        self.final_capacity = np.zeros(shape=(self.num_years,)) # Initialize dynamic, auxilliary variable with zeros
        self.cost_fun_params = {"sizing_constant": cp.Parameter(shape=(self.num_years,),
                                                                nonneg=True)}
        self.conversion_fun_params_2 = {"maximum_size": cp.Parameter(shape=(self.num_years,),
                                                                nonneg=True)}
        self.conversion_fun_params_3 = {"minimum_size": cp.Parameter(shape=(self.num_years,),
                                                                nonneg=True)}
        return
    
    def build_edge(self, edge_number):
        target_node_time = self.target_node_times[edge_number]
        new_edge = Edge_STEVFNs()
        self.edges += [new_edge]
        new_edge.attach_target_node(self.network.extract_node(
            self.target_node_location, self.target_node_type, target_node_time))
        # EDITED:
        # Initialize existing flows as zero if final_capacity is not updated yet to determine flow
        index_number = 0 # Use only initial capacity from final_capacity array at this stage
        new_edge.flow = (self.flows[index_number] * self.gen_profile[edge_number])
        return
    
    def build_edge_2(self):
        ''' Build a second edge to constrain maximum capacity'''
        source_node_type = "NULL"
        source_node_location = self.source_node_location_2
        source_node_time = 0
        target_node_type = self.target_node_type_2
        target_node_location = self.target_node_location_2
        target_node_time = self.target_node_time_2
       
        new_edge = Edge_STEVFNs()
        self.edges += [new_edge]
        if source_node_type != "NULL":
            new_edge.attach_source_node(self.network.extract_node(
                source_node_location, source_node_type, source_node_time))
        if target_node_type != "NULL":
            new_edge.attach_target_node(self.network.extract_node(
                target_node_location, target_node_type, target_node_time))
        new_edge.flow = self.flows # capacities, CVXPY variable
        new_edge.conversion_fun = self.conversion_fun_2
        new_edge.conversion_fun_params = self.conversion_fun_params_2
        return
    
    def build_edge_3(self):
        ''' Build a third edge to constrain maximum capacity'''
        source_node_type = "RE_WIND"
        source_node_location = self.source_node_location_3
        source_node_time = 0
        target_node_type = self.target_node_type_3
        target_node_location = self.target_node_location_3
        target_node_time = self.target_node_time_3
        
        new_edge = Edge_STEVFNs()
        self.edges += [new_edge]
        if source_node_type != "NULL":
            new_edge.attach_source_node(self.network.extract_node(
                source_node_location, source_node_type, source_node_time))
        if target_node_type != "NULL":
            new_edge.attach_target_node(self.network.extract_node(
                target_node_location, target_node_type, target_node_time))
        new_edge.flow = self.flows # capacities, CVXPY variable
        new_edge.conversion_fun = self.conversion_fun_3
        new_edge.conversion_fun_params = self.conversion_fun_params_3
        return
    
    def build_edges(self):
        self.edges = []
        for counter1 in range(self.number_of_edges):
            self.build_edge(counter1)
        self.build_edge_2()
        # self.build_edge_3()
        return
    
    def _update_flows(self):
        '''NEW FUNCTION: Allows power flow update for multi-year modeling for RE assets'''
        index_number = 0 # indicates the year for each edge
        edge_counter = 0
        # Loop through all edges from build_edge, not edge_2 or edge_3
        for edge in self.edges[:self.number_of_edges]:
            if edge_counter >= self.year_change_indices[index_number]:
                if index_number < self.num_years-1:
                    if edge_counter == self.year_change_indices[index_number+1]:
                        index_number += 1
                
                # Update value of flow per edge
                edge.flow = self.final_capacity[index_number] * self.gen_profile[edge_counter]
                edge_counter += 1
        return
    
    def _update_capacities(self):
        """Update existing capacities dynamically for multi-year optimization."""
    
        historic_capacities = self._get_cumulative_capacities_array().tolist()  # Ensure list for handling CVXPY variables
        
        # Create an empty list to hold expressions
        final_capacity_expressions = []
        
        # Initialize cumulative capacity with historical values
        cumulative_capacity = historic_capacities.copy()
    
        for year in range(self.num_years):
            if year == 0:
                # First year: Capacity starts with existing values
                final_capacity_expressions.append(cumulative_capacity[year])
            else:
                # Subsequent years: Add new installed capacity dynamically
                new_installed = self.flows[year - 1]  # CVXPY variable
                
                # Ensure cumulative capacity updates dynamically as an expression
                cumulative_capacity[year] = cumulative_capacity[year] + new_installed
                final_capacity_expressions.append(cumulative_capacity[year])
        # Convert to a CVXPY expression array
        self.final_capacity = cp.hstack(final_capacity_expressions)  # Concatenates a series of expressions
    
    def process_csv_values(self,values):
        """Method converts a comma-separated string to a NumPy array of floats or returns
        the original numeric values in an array."""
        if isinstance(values, str):
            return np.array([float(x) for x in values.split(",")], dtype=float)
        return np.array(values, dtype=float)  # Ensure it's always a NumPy array


    def _update_sizing_constant(self):
        """Updates the sizing constant with NPV discounting applied year-by-year."""
        num_years = self.num_years  # Number of years being modeled
    
        # Convert discount rate to float
        discount_rate = float(self.network.system_parameters_df.loc["discount_rate", "value"])
    
        # Extract and process the original sizing_constant from the parameters DataFrame
        original_sizing_constant = self.process_csv_values(self.parameters_df["sizing_constant"])
    
        # Ensure the array length matches num_years
        if len(original_sizing_constant) != num_years:
            raise ValueError("Mismatch between num_years and sizing_constant length")
    
        # Apply NPV discounting: Keep the first value unchanged, discount the rest
        adjusted_sizing_constant = original_sizing_constant / np.array([(1 + discount_rate) ** t for t in range(num_years)])
    
        # Store updated values
        self.cost_fun_params["sizing_constant"].value = adjusted_sizing_constant
    
    
    def _update_parameters(self):
        """Updates model parameters efficiently by processing cost projections, max capacities, and min capacities."""
    
        # Update cost function parameters
        for parameter_name, parameter in self.cost_fun_params.items():
            parameter.value = self.process_csv_values(self.parameters_df[parameter_name])
    
        # Update conversion function parameters for max and min capacities
        for param_dict in [self.conversion_fun_params_2, self.conversion_fun_params_3]:
            for parameter_name, parameter in param_dict.items():
                parameter.value = self.process_csv_values(self.parameters_df[parameter_name])
    
        # Update costs and RE profile
        self._update_sizing_constant()
        self._load_RE_profile()
        # Build and update values for existing capacities
        self._build_existing_capacities_matrix()
        self._get_cumulative_capacities_array()
        self._update_capacities()
        self._update_flows()
    
    def update(self, asset_type):
        self._load_parameters_df(asset_type)
        self._load_historic_capacity_params()
        self._update_parameters()
        return
    
    def _load_RE_profile(self):
        """This function reads file and updates self.gen_profile """
        lat_lon_df = self.network.lat_lon_df.iloc[self.target_node_location]
        lat = lat_lon_df["lat"]
        lat = np.int64(np.round((lat) / 0.5)) * 0.5
        lat = min(lat,90.0)
        lat = max(lat,-90.0)
        LAT = "{:0.1f}".format(lat)
        lon = lat_lon_df["lon"]
        lon = np.int64(np.round((lon) / 0.625)) * 0.625
        lon = min(lon, 179.375)
        lon = max(lon, -180.0)
        LON = str(lon)
        RE_TYPE = self.parameters_df["RE_type"]
        profile_folder = os.path.join(self.parameters_folder, "profiles", RE_TYPE, r"lat"+LAT)
        profile_filename = RE_TYPE + r"_lat" + LAT + r"_lon" + LON + r".csv"
        profile_filename = os.path.join(profile_folder, profile_filename)
        full_profile = np.loadtxt(profile_filename)
        set_size = self.parameters_df["set_size"]
        set_number = self.parameters_df["set_number"]
        n_sets = int(np.ceil(self.number_of_edges/set_size))
        gap = int(len(full_profile) / (n_sets * set_size)) * set_size
        offset = set_size * set_number
        new_profile = np.zeros(int(n_sets * set_size))
        # NEW ADDITION: Initialize indices and variables to Build multi-year profiles
        hour_counter = 1
        missing_val = 0
        # --
        for counter1 in range(n_sets):
            old_loc_0 = offset + gap*counter1
            old_loc_1 = old_loc_0 + set_size
            new_loc_0 = set_size * counter1
            new_loc_1 = new_loc_0 + set_size
            new_profile[new_loc_0 : new_loc_1] = full_profile[old_loc_0 : old_loc_1]
            # -- NEW ADDITION: Get indices for change in year when day sampling
            if old_loc_0 > (hour_counter * 8759) + missing_val:
                 self.year_change_indices.append(new_loc_0)
                 hour_counter += 1
                 missing_val += 1
        self.gen_profile.value = new_profile[:self.number_of_edges]
        return
    
    def _build_existing_capacities_matrix(self):
        '''NEW FUNCTION
        Builds the matrix with installed capacities each year based on historic
        total installed capacities'''
        if self.historic_capacity_df is None:
            raise ValueError("Error: historic_capacity_df is None. It must be loaded before building the capacities matrix.")
    
        self.historic_capacity_df = self.historic_capacity_df[['year', 'wind_installed_capacity_GW']].dropna()
        # Calculate annual installed capacity
        self.historic_capacity_df['annual_installed_capacity'] = self.historic_capacity_df['wind_installed_capacity_GW'].diff().fillna(0)
        
        # Initialize an empty DataFrame with the Year column
        self.asset_lifetime = int(self.parameters_df["lifespan"] / 8760)
        start_year = int(self.historic_capacity_df['year'].min())
        end_year = int(self.historic_capacity_df['year'].max()) + self.asset_lifetime  
    
        self.existing_capacity_df = pd.DataFrame({'Year': range(start_year, end_year + 1)})
    
        # Ensure self.existing_capacity_df is not accidentally None
        if self.existing_capacity_df is None or self.existing_capacity_df.empty:
            raise ValueError("Error: self.existing_capacity_df was not created properly.")
    
        for idx, row in self.historic_capacity_df.iterrows():
            year = int(row['year'])
            annual_capacity = float(row['annual_installed_capacity'])
            self._add_new_capacities(year, annual_capacity)

    

        
    def _add_new_capacities(self, current_year, annual_capacity):
        """NEW FUNCTION
        Calculates the annual installed capacity from historical data of total
        installed capacites to add that year to matrix with asset lifetime
        """
        # Add the new column if it doesn't exist
        if str(current_year) not in self.existing_capacity_df.columns:
            self.existing_capacity_df[str(current_year)] = pd.Series(0, index=self.existing_capacity_df.index, dtype="float64") # Initialize the column with zeros
        
        # Get the starting index for the current year
        start_idx = self.existing_capacity_df[self.existing_capacity_df['Year'] == current_year].index[0]
        # Fill the next column for diagonal block for the current year
        for row in range(self.asset_lifetime):  # Fill exactly asset's lifetime in years
            if start_idx + row < len(self.existing_capacity_df):
                self.existing_capacity_df.at[start_idx + row, str(current_year)] = annual_capacity

    
    def _add_optimized_capacities_to_matrix(self):
        '''NEW FUNCTION
        Adds the optimal capacities from problem to the matrix
        '''
        # Iterate through control horizon
        for year in range(self.num_years):
            # Get start year for scenario
            start_year = int(self.network.system_parameters_df.loc["scenario_start", "value"])
            # Add column for the newly installed capacity being optimised 
            self.existing_capacity_df = self._add_new_capacities(start_year+year, self.flows[year])
        return self.existing_capacity_df 

    def _get_cumulative_capacities_array(self):
        '''
        NEW FUNCTION
        Generates the array for the cumulative installed capacities for the years
        in the control horizon
        '''
        start_year = int(self.network.system_parameters_df.loc["scenario_start", "value"])
        end_year = start_year + int(self.network.system_parameters_df.loc["control_horizon", "value"] / 8760)
    
        # Filter rows within the desired year range
        filtered_df = self.existing_capacity_df[(self.existing_capacity_df['Year'] >= start_year) & 
                                                (self.existing_capacity_df['Year'] < end_year)]

        # Sum all columns for each row (excluding the 'Year' column) to get cumulative capacities array
        cumulative_capacities = filtered_df.iloc[:, 1:].sum(axis=1).to_numpy()

        return cumulative_capacities

    def _calculate_min_max_capacities(self):
        """
        Computes dynamic min and max capacity constraints for each year.
    
        Returns:
            (list, list): Tuple of min and max capacity limits per year.
        """
        # Initialize variables
        start_year = int(self.network.system_parameters_df.loc["scenario_start", "value"])
        end_year = start_year + 30
        dt = 1
        years = np.arange(start_year, end_year + dt, dt)
        num_years = len(years)
        k_goal = 150 # Define capacity goal from other model
        r_max = 10
        # k_goal = self.parameters_df["goal_capacity"]
        # r_max = self.parameters_df["max_rate_adoption"]
        k_existing_array = self.final_capacity.value.flatten()
        k_min_list = []
        k_max_list = []
    
        for n in range(num_years):
            if n > 0:  # Update existing capacity with previously installed self.flow
                k_existing_array.append(k_existing_array[n - 1] + k_min_list[n - 1])
    
            years_left = (end_year - start_year) - (n * dt)
    
            # Compute max and min constraints
            k_max = min(
                k_goal - k_existing_array[n],
                (r_max * dt)
            )
    
            k_min = max((k_goal - (r_max * years_left)), k_existing_array[n]) - k_existing_array[n]
    
            k_max_list.append(k_max)
            k_min_list.append(k_min)
            
        # To relate to params in the cost function
        self.cost_fun_params["min_capacity"] = k_min_list
        
        return k_min_list, k_max_list
    

    def get_plot_data(self):
        '''
        Gets total power flow data for each timestep, including from existing and
        newly built capacities

        Returns
        -------
        total_flows : list
            List of flows from this asset.

        '''
        total_flows = []
        for edge in self.edges:
            total_flows.append(edge.flow.value)
        return total_flows 
    
    def size(self):
        # Returns size of asset for Existing RE, which is a vector #
        return self.flows.value
    
    def asset_size(self):
        # Returns size of asset for Existing RE, which is a vector #
        return self.flows.value
    
    def get_asset_sizes(self):
        # Returns the size of the asset as a dict #
        asset_size = self.size()
        asset_identity = self.asset_name + r"_" + self.parameters_df["RE_type"] + r"_location_" + str(self.target_node_location)
        return {asset_identity: asset_size}