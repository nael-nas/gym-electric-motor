from examples.agents.simple_controllers import Controller
import time
import sys, os

sys.path.append(os.path.abspath(os.path.join('..')))
import gym_electric_motor as gem
from gym_electric_motor import reference_generators as rg
from gym_electric_motor.visualization import MotorDashboard

"""
Run this file from within the 'examples' folder:
>> cd examples
>> python perm_DC_omega.py

Description:
        Environment to control a  permanently excited DC motor.
        Controlled Quantity: 'omega'
        Limitations: Physical limitations of the motor will be Current.
        Converter : FourQuadrantConverter from converters.py
"""

if __name__ == '__main__':

    """
       Continuous mode: The action is the average (normalized) voltage per time step which is assumed to be transferred to a PWM/SVM 
                        converter to generate the switching sequence.

       Discrete mode: The action is the switching state of the power converter i.e., a quantity from a discrete set of
                      switching states which can be generated by the converter.     
    """
    env = gem.make(
        'DcPermExDisc-v1',
        visualization=MotorDashboard(plots=['omega', 'torque', 'i', 'u', 'u_sup'], visu_period=1),
        ode_solver='scipy.solve_ivp', solver_kwargs=dict(),
        reference_generator=rg.SwitchedReferenceGenerator(
            sub_generators=[
                rg.SinusoidalReferenceGenerator, rg.WienerProcessReferenceGenerator(), rg.StepReferenceGenerator()
            ], p=[0.1, 0.8, 0.1], super_episode_length=(1000, 10000)
        )
    )

    # Assign a simple on/off controller
    controller = Controller.make('on_off', env)
    state, reference = env.reset()
    start = time.time()
    cum_rew = 0
    for i in range(100000):
        env.render()
        action = controller.control(state, reference)
        (state, reference), reward, done, _ = env.step(action)
        if done:
            env.reset()
        cum_rew += reward
    print(cum_rew)
