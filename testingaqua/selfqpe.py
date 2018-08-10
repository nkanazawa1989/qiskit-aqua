import logging

from functools import reduce
import numpy as np
from qiskit import QuantumRegister, ClassicalRegister, QuantumCircuit, execute
from qiskit.tools.qi.pauli import Pauli
from qiskit_aqua import Operator, QuantumAlgorithm, AlgorithmError
from qiskit_aqua import get_initial_state_instance, get_iqft_instance
from qiskit import available_backends, execute, register, get_backend
import matplotlib.pyplot as plt
from qiskit.tools.visualization import plot_histogram


from qiskit_aqua.input import get_input_instance

logger = logging.getLogger(__name__)

try:
    import sys
    sys.path.append("~/workspace/") # go to parent dir
    import Qconfig
    qx_config = {
        "APItoken": Qconfig.APItoken,
        "url": Qconfig.config['url']}
except Exception as e:
    print(e)
    qx_config = {
        "APItoken":"bad8fd2aba4b1154108dec4b307471b8c20f32afe6b98e59b723f29c0bfc455d4b19e7783ce8d60cd52369909a15349d0d571d1246dedc43ffc21e03ca13a07a",
        "url":"https://quantumexperience.ng.bluemix.net/api"}
register(qx_config['APItoken'], qx_config['url'])

backend = "local_qasm_simulator"

operator = None
state_in = None
#state_in.append([1])
num_time_slices = 1
paulis_grouping = 'random'
expansion_mode = 'suzuki'
expansion_order = 3
num_ancillae = 7
ancilla_phase_coef = 1
circuit = None
ret = {}
b = [1]
b = b.append( [1])
matr = np.array([[0.125, 0], [0,0.5]])
qubit0p = Operator(matrix=matr)
operator = qubit0p

state_in=get_initial_state_instance('CUSTOM')
state_in.init_args(num_qubits=num_ancillae, state_vector = b)

iqft = get_iqft_instance('STANDARD')
iqft.init_args(num_qubits = num_ancillae)



if circuit is None:
    operator._check_representation('paulis')
    print(operator.print_operators('matrix'))
    ret['translation'] = sum([abs(p[0]) for p in operator.paulis])
    ret['stretch'] = 0.5 / ret['translation']

        # translate the operator
    operator._simplify_paulis()
    translation_op = Operator([
        [
            ret['translation'],
            Pauli(
                np.zeros(operator.num_qubits),
                np.zeros(operator.num_qubits)
            )
        ]
    ])
    translation_op._simplify_paulis()
    print(translation_op.print_operators('paulis'))
    operator += translation_op

        # stretch the operator
    for p in operator._paulis:
        p[0] = p[0] * ret['stretch']

        # check for identify paulis to get its coef for applying global phase shift on ancillae later
    num_identities = 0
    for p in operator.paulis:
        if np.all(p[1].v == 0) and np.all(p[1].w == 0):
            num_identities += 1
            if num_identities > 1:
                raise RuntimeError('Multiple identity pauli terms are present.')
            ancilla_phase_coef = p[0].real if isinstance(p[0], complex) else p[0]

    a = QuantumRegister(num_ancillae, name='a')
    c = ClassicalRegister(num_ancillae, name='c')
    q =  QuantumRegister(operator.num_qubits, name='q')
    qc = QuantumCircuit(a, q, c)

        # initialize state_in
    qc.data += state_in.construct_circuit('circuit', q).data

        # Put all ancillae in uniform superposition
    qc.u2(0, np.pi, a)

        # phase kickbacks via dynamics
    pauli_list = operator.reorder_paulis(grouping=paulis_grouping)
    if len(pauli_list) == 1:
        slice_pauli_list = pauli_list
    else:
        if expansion_mode == 'trotter':
            slice_pauli_list = pauli_list
        elif expansion_mode == 'suzuki':
            slice_pauli_list = Operator._suzuki_expansion_slice_pauli_list(
                pauli_list,
                1,
                expansion_order
            )
        else:
            raise ValueError('Unrecognized expansion mode {}.'.format(expansion_mode))
    for i in range(num_ancillae):
        qc.data += operator.construct_evolution_circuit(
            slice_pauli_list, -2 * np.pi, num_time_slices, q, a, ctl_idx=i
        ).data
            # global phase shift for the ancilla due to the identity pauli term
        #qc.u1(2 * np.pi * ancilla_phase_coef * (2 ** i), a[i])

        # inverse qft on ancillae
    iqft.construct_circuit('circuit', a, qc)

        # measuring ancillae
    qc.measure(a, c)

    circuit = qc
    logger.info('QPE circuit qasm length is roughly {}.'.format(
        len(circuit.qasm().split('\n'))
    ))
results = execute(circuit, backend=backend, shots=1000).result()

rd = results.get_counts(circuit)
rets = sorted([(rd[k], k) for k in rd])[::-1]
ret = rets[0][-1][::-1]
retval = sum([t[0] * t[1] for t in zip(
    [1 / 2 ** p for p in range(1, num_ancillae + 1)],
    [int(n) for n in ret]
)])

#ret['measurements'] = rets
#ret['top_measurement_label'] = ret
#ret['top_measurement_decimal'] = retval
#ret['energy'] = retval / ret['stretch'] - ret['translation']

print(results)
print(operator.print_operators('paulis'))
print(operator.print_operators('matrix'))

plot_histogram(rd)
#print(ret)