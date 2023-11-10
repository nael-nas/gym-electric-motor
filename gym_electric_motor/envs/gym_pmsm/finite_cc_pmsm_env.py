from gym_electric_motor.core import (
    ElectricMotorEnvironment,
    ReferenceGenerator,
    RewardFunction,
    ElectricMotorVisualization,
)
from gym_electric_motor.physical_systems.physical_systems import SynchronousMotorSystem
from gym_electric_motor.visualization import MotorDashboard
from gym_electric_motor.reference_generators import (
    WienerProcessReferenceGenerator,
    MultipleReferenceGenerator,
)
from gym_electric_motor import physical_systems as ps
from gym_electric_motor.reward_functions import WeightedSumOfErrors
from gym_electric_motor.utils import initialize
from gym_electric_motor.constraints import SquaredConstraint


class FiniteCurrentControlPermanentMagnetSynchronousMotorEnv(ElectricMotorEnvironment):
    """
    Description:
        Environment to simulate a finite control set current controlled permanent magnet synchr. motor.

    Key:
        ``'Finite-CC-PMSM-v0'``

    Default Components:
        - Supply: :py:class:`.IdealVoltageSupply`
        - Converter: :py:class:`.FiniteB6BridgeConverter`
        - Motor: :py:class:`.PermanentMagnetSynchronousMotor`
        - Load: :py:class:`.ConstantSpeedLoad`
        - Ode-Solver: :py:class:`.EulerSolver`

        - Reference Generator: :py:class:`.WienerProcessReferenceGenerator` *Reference Quantity:* ``'i_sd', 'i_sq``

        - Reward Function: :py:class:`.WeightedSumOfErrors` reward_weights: ``'i_sd' = 0.5, 'i_sq' = 0.5``

        - Visualization: :py:class:`.MotorDashboard` current and action plots

        - Constraints: :py:class:`.SquaredConstraint` on the currents  ``'i_sd', 'i_sq'``

    State Variables:
        ``['omega' , 'torque', 'i_sd', 'i_sq', 'i_a', 'i_b', 'i_c', 'u_sd', 'u_sq', 'u_a', 'u_b', 'u_c', 'u_sup']``

    Reference Variables:
        ``['i_sd', 'i_sq']``

    Control Cycle Time:
        tau = 1e-5 seconds

    Observation Space:
        Type: Tuple(State_Space, Reference_Space)

    State Space:
        Box(low=13 * [-1], high=13 * [1])

    Reference Space:
        Box(low=[-1, -1], high=[1, 1])

    Action Space:
        Discrete(8)

    Initial State:
        Zeros on all state variables.

    Example:
        >>> import gym_electric_motor as gem
        >>> from gym_electric_motor.reference_generators import LaplaceProcessReferenceGenerator
        >>>
        >>> # Select a different ode_solver with default parameters by passing a keystring
        >>> my_overridden_solver = 'scipy.solve_ivp'
        >>>
        >>> # Update the default arguments to the voltage supply by passing a parameter dict
        >>> my_changed_voltage_supply_args = {'u_nominal': 400.0}
        >>>
        >>> # Replace the reference generator by passing a new instance
        >>> my_new_ref_gen_instance = LaplaceProcessReferenceGenerator(
        ...     reference_state='i_sq',
        ...     sigma_range=(1e-3, 1e-2)
        ... )
        >>> env = gem.make(
        ...     'Finite-CC-PMSM-v0',
        ...     voltage_supply=my_changed_voltage_supply_args,
        ...     ode_solver=my_overridden_solver,
        ...     reference_generator=my_new_ref_gen_instance
        ... )
        >>> terminated = True
        >>> for _ in range(1000):
        >>>     if terminated:
        >>>         state, reference = env.reset()
        >>>     (state, reference), reward, terminated, truncated, _ = env.step(env.action_space.sample())
    """

    def __init__(
        self,
        supply=None,
        converter=None,
        motor=None,
        load=None,
        ode_solver=None,
        reward_function=None,
        reference_generator=None,
        visualization=None,
        state_filter=None,
        callbacks=(),
        constraints=(SquaredConstraint(("i_sq", "i_sd")),),
        calc_jacobian=True,
        tau=1e-5,
        physical_system_wrappers=(),
        **kwargs,
    ):
        """
        Args:
            supply(env-arg): Specification of the :py:class:`.VoltageSupply` for the environment
            converter(env-arg): Specification of the :py:class:`.PowerElectronicConverter` for the environment
            motor(env-arg): Specification of the :py:class:`.ElectricMotor` for the environment
            load(env-arg): Specification of the :py:class:`.MechanicalLoad` for the environment
            ode_solver(env-arg): Specification of the :py:class:`.OdeSolver` for the environment
            reward_function(env-arg): Specification of the :py:class:`.RewardFunction` for the environment
            reference_generator(env-arg): Specification of the :py:class:`.ReferenceGenerator` for the environment
            visualization(env-arg): Specification of the :py:class:`.ElectricMotorVisualization` for the environment
            constraints(iterable(str/Constraint)): All Constraints of the environment. \n
                - str: A LimitConstraints for states (episode terminates, if the quantity exceeds the limit)
                 can be directly specified by passing the state name here (e.g. 'i', 'omega') \n
                - instance of Constraint: More complex constraints (e.g. the SquaredConstraint can be initialized and
                 passed to the environment.
            calc_jacobian(bool): Flag, if the jacobian of the environment shall be taken into account during the
                simulation. This may lead to speed improvements. Default: True
            tau(float): Duration of one control step in seconds. Default: 1e-4.
            state_filter(list(str)): List of states that shall be returned to the agent. Default: None (no filter)
            callbacks(list(Callback)): Callbacks for user interaction. Default: ()
            physical_system_wrappers(list(PhysicalSystemWrapper)): List of Physical System Wrappers to modify the
            actions to and states from the physical system before they are used in the environment. Default: ()

        Note on the env-arg type:
            All parameters of type env-arg can be selected as one of the following types:

            **instance:** Pass an already instantiated object derived from the corresponding base class
            (e.g. ``reward_function=MyRewardFunction()``). This is directly used in the environment.

            **dict:** Pass a dict to update the default parameters of the default type.
            (e.g. ``visualization=dict(state_plots=('omega', 'u'))``)

            **str:** Pass a string out of the registered classes to select a different class for the component.
            This class is then initialized with its default parameters.
            The available strings can be looked up in the documentation. (e.g. ``converter='Finite-2QC'``)
        """
        default_sub_generators = (
            WienerProcessReferenceGenerator(reference_state="i_sd"),
            WienerProcessReferenceGenerator(reference_state="i_sq"),
        )

        physical_system = SynchronousMotorSystem(
            supply=initialize(
                ps.VoltageSupply, supply, ps.IdealVoltageSupply, dict(u_nominal=420.0)
            ),
            converter=initialize(
                ps.PowerElectronicConverter,
                converter,
                ps.FiniteB6BridgeConverter,
                dict(),
            ),
            motor=initialize(
                ps.ElectricMotor, motor, ps.PermanentMagnetSynchronousMotor, dict()
            ),
            load=initialize(
                ps.MechanicalLoad, load, ps.ConstantSpeedLoad, dict(omega_fixed=100.0)
            ),
            ode_solver=initialize(ps.OdeSolver, ode_solver, ps.ScipyOdeSolver, dict()),
            calc_jacobian=calc_jacobian,
            tau=tau,
        )
        reference_generator = initialize(
            ReferenceGenerator,
            reference_generator,
            MultipleReferenceGenerator,
            dict(sub_generators=default_sub_generators),
        )
        reward_function = initialize(
            RewardFunction,
            reward_function,
            WeightedSumOfErrors,
            dict(reward_weights=dict(i_sd=0.5, i_sq=0.5)),
        )
        visualization = initialize(
            ElectricMotorVisualization,
            visualization,
            MotorDashboard,
            dict(state_plots=("i_sd", "i_sq"), action_plots="all"),
        )
        super().__init__(
            physical_system=physical_system,
            reference_generator=reference_generator,
            reward_function=reward_function,
            constraints=constraints,
            visualization=visualization,
            state_filter=state_filter,
            callbacks=callbacks,
            physical_system_wrappers=physical_system_wrappers,
            **kwargs,
        )
