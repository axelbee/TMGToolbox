#---LICENSE----------------------
'''
    Copyright 2015 Travel Modelling Group, Department of Civil Engineering, University of Toronto

    This file is part of the TMG Toolbox.

    The TMG Toolbox is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    The TMG Toolbox is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with the TMG Toolbox.  If not, see <http://www.gnu.org/licenses/>.
'''
#---METADATA---------------------
'''
Apply Batch Line Edits

    Authors: mattaustin222

    Latest revision by: mattaustin222
    
    
    This tool brings in a list of changes to be applied to transit lines
    in a set of scenarios. The aim of the tool is to reduce the 
    work required in making sweeping changes to headways and speeds
    of transit lines. It is intended only to be called from XTMF.
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2015-02-24 by mattaustin222
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
from HTMLParser import HTMLParser
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
netCalc = _MODELLER.tool('inro.emme.network_calculation.network_calculator')

##########################################################################################################

class ApplyBatchLineEdits(_m.Tool()):
    
    version = '0.0.1'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here

    COLON = ':'
    COMMA = ','
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    xtmf_ScenarioNumber = _m.Attribute(int) # parameter used by XTMF only

    InstructionFile = _m.Attribute(str) # file should have the following header: 
                                        # filter|x_hdwchange|x_spdchange
                                        # where filter is a network calculator filter expression
                                        # x refers to the scenario number
                                        # the x columns can be multiple (ie. multiple definitions
                                        # in a single file)
                                        # hdwchange and spdchange are factors by which
                                        # to change headways and speeds for the filtered
                                        # lines

    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario
    
    def page(self):
                
        pb = _m.ToolPageBuilder(self, title="Apply Batch Line Edits",
                     description="Cannot be called from Modeller.",
                     runnable=False,
                     branding_text="XTMF")
        
        return pb.render()
    
    ##########################################################################################################
        
    def __call__(self, xtmf_ScenarioNumber, inputFile):
        
        #---1 Set up scenario
        self.Scenario = _m.Modeller().emmebank.scenario(xtmf_ScenarioNumber)
        if (self.Scenario == None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)

        #---2 Set up instruction file
        self.InstructionFile = inputFile
        if (self.InstructionFile == None):
            raise Exception("Need to provide an input file.")

        try:
            self._Execute()
        except Exception, e:
            msg = str(e) + "\n" + _traceback.format_exc(e)
            raise Exception(msg)

    ##########################################################################################################    
        
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):

            changesToApply = self._LoadFile()
            print "Instruction file loaded"
            if changesToApply: 
                self._ApplyLineChanges(changesToApply)
                print "Headway and speed changes applied"
            else:
                print "No changes available in this scenario"

            self.TRACKER.completeTask()


    ##########################################################################################################    
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 

    def _LoadFile(self):
        with open(self.InstructionFile) as reader:
            header = reader.readline()
            cells = header.strip().split(self.COMMA)
            
            filterCol = cells.index('filter')
            headwayTitle = self.Scenario.id + '_hdwchange'
            speedTitle = self.Scenario.id + '_spdchange'
            try:
                headwayCol = cells.index(headwayTitle)
            except Exception, e:
                msg = "Error. No headway match for specified scenario: '%s'." %self.Scenario.id
                _m.logbook_write(msg)
                print msg
                return
            try:
                speedCol = cells.index(speedTitle)
            except Exception, e:
                msg = "Error. No speed match for specified scenario: '%s'." %self.Scenario.id
                _m.logbook_write(msg)
                print msg
                return

            instructionData = {}
            
            for num, line in enumerate(reader):
                cells = line.strip().split(self.COMMA)
                
                filter = cells[filterCol]
                if cells[headwayCol]:
                    hdw = cells[headwayCol]
                else:
                    hdw = 1 # if the headway column is left blank, carry forward a factor of 1
                if cells[speedCol]:
                    spd = cells[speedCol]
                else:
                    spd = 1
                instructionData[filter] = (float(hdw),float(spd))
        
        return instructionData

    def _ApplyLineChanges(self, inputData):
        for filter, factors in inputData.iteritems():
            if factors[0] != 1:
                spec = {
                    "type": "NETWORK_CALCULATION",
                    "expression": str(factors[0]) + "*hdw",
                    "result": "hdw",
                    "selections": {
                        "transit_line": filter}}
                netCalc(spec, self.Scenario)
            if factors[1] != 1:
                spec = {
                    "type": "NETWORK_CALCULATION",
                    "expression": str(factors[1]) + "*speed",
                    "result": "speed",
                    "selections": {
                        "transit_line": filter}}
                netCalc(spec, self.Scenario)

    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
            