"""Prespecified R1 repair, audited 13 September 2026.
Apply only to an isolated loaded copy of the original classical module.
This fixes a training/prediction-coordinate mismatch; it does not reconstruct
an official CPI basket or turn synthetic category indices into official CPI.
No forecast register or original input file is modified by this function.
"""
def harmonize_training_features(classical_module):
    m = classical_module
    synthetic_yoy = 100.0 * (m.L / m.L.shift(12) - 1.0)
    revised = m.Y.copy()
    revised.loc[:, m.COMP] = synthetic_yoy.loc[:, m.COMP]
    m.Y = revised
    return m
