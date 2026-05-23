# DYNAMIC ENERGY 
# general 
_NAND_DYN = 1
_NOR_DYN = 1
_XNOR_DYN = 1
_AND_DYN = 1        
_NOT_DYN = 1       
_OR_DYN = 1  
_MUX_DYN = 1
_REG_DYN = 1
_CMP_DYN = 1
_XOR_DYN = 1
_RNG_DYN = 1
_CTR_DYN = 1
_ADD_DYN = 1
_SUB_DYN = _ADD_DYN
_BSHIFT_DYN = 1
_INC_DYN = 1


#uGEMM specific
_BSG_DYN = _RNG_DYN + _CMP_DYN
_ACC_DYN = 1
_PC_DYN = 1
_MIN_DYN = 1


#uSystolic specific
_SHIFT_DYN = 1
_FIFO_DYN = 1
_SEL_DYN = 1


#Cambricon-U specifc
_HA_DYN = 1
_RIM_INC_DYN = 1
_RIM_RD_DYN = 1
_BIN_CONV_DYN = 1
_SKEW_CELL_DYN = 1
_SKEW_PC_DYN = 1

# Binary specific
_MAC_BINARY_INT8_DYN = 1 


#LEAKAGE POWER
# general 
_NAND_LEAK = 1
_NOR_LEAK = 1
_XNOR_LEAK = 1
_AND_LEAK = 1        
_NOT_LEAK = 1       
_OR_LEAK = 1  
_MUX_LEAK = 1
_REG_LEAK = 1
_CMP_LEAK = 1
_XOR_LEAK = 1
_RNG_LEAK = 1
_CTR_LEAK = 1
_ADD_LEAK = 1
_SUB_LEAK = _ADD_LEAK
_BSHIFT_LEAK = 1
_INC_LEAK = 1


#uGEMM specific
_BSG_LEAK = _RNG_LEAK + _CMP_LEAK
_ACC_LEAK = 1
_PC_LEAK = 1
_MIN_LEAK = 1


#uSystolic specific
_SHIFT_LEAK = 1
_FIFO_LEAK = 1
_SEL_LEAK = 1


#Cambricon-U specifc
_HA_LEAK = 1
_RIM_INC_LEAK = 1
_RIM_RD_LEAK = 1
_BIN_CONV_LEAK = 1
_SKEW_CELL_LEAK = 1
_SKEW_PC_LEAK = 1

# Binary specific
_MAC_BINARY_INT8_LEAK = 1 