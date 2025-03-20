#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Mar 19 14:34:09 2025

@author: Mónica Sagastuy-Breña
Based on CO2_Budget Asset code for single-year model by @author: Aniq Ahsan
"""

import os
import numpy as np
import cvxpy as cp
from ..Base_Assets import Asset_STEVFNs
from ...Network import Edge_STEVFNs


class CO2_Budget_MY_Asset(Asset_STEVFNs):
    """Class of CO2 emissions budget asset for multi-year modeling """
    asset_name = "CO2_Budget_MY"
    source_node_type = "NULL"
    source_node_time = 0 # Only one CO2 budget defined at the start of the project, vector that reduces with time
    target_node_type = "CO2_Budget"
    period = 1
    transport_time = 0
    
    @staticmethod
    def conversion_fun(flows, params):
        return params["maximum_budget"]
    
    def __init__(self):
        super().__init__()
        self.conversion_fun_params = {"maximum_budget": cp.Parameter(nonneg=True)}
        return
        
    
    def define_structure(self, asset_structure):
        self.asset_structure = asset_structure
        self.num_years = int(self.network.system_parameters_df.loc["control_horizon", "value"] / 8760)
        self.source_node_location = 0
        self.source_node_times = np.array([self.source_node_time])
        self.target_node_location = 0
        self.number_of_edges = self.num_years
        self.target_node_times = np.arrange(0, self.number_of_edges)
        self.flows = cp.Constant(np.zeros(self.number_of_edges))
        self.conversion_fun_params = {"maximum_budget": cp.Parameter(shape=(self.number_of_edges),
                                                                     nonneg=True)}
        return
    
    def build_edge(self, edge_number):
        source_node_time = self.source_node_times[edge_number]
        target_node_time = self.target_node_times[edge_number]
        new_edge = Edge_STEVFNs()
        self.edges += [new_edge]
        if self.source_node_type != "NULL":
            new_edge.attach_source_node(self.network.extract_node(
                self.source_node_location, self.source_node_type, source_node_time))
        if self.target_node_type != "NULL":
            new_edge.attach_target_node(self.network.extract_node(
                self.target_node_location, self.target_node_type, target_node_time))
        new_edge.flow = self.flows[edge_number]
        new_edge.conversion_fun = self.conversion_fun
        new_edge.conversion_fun_params = self.conversion_fun_params
        return
    
    def _update_parameters(self):
        """Updates model parameters by processing csv values for """
    
        # Update cost function parameters
        for parameter_name, parameter in self.cost_fun_params.items():
            parameter.value = self.process_csv_values(self.parameters_df[parameter_name])
    
    def get_plot_data(self):
        return self.flows.value
    
    
    def component_size(self):
        # Returns size of component (i.e. asset) #
        return (self.edges[0].target_node.net_output_flows + self.conversion_fun_params["maximum_budget"]).value
    

