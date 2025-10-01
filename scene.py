from manim import *

class Intro(Scene):
    def construct(self):
        t = Text("Hello, Manim!").scale(0.9)
        self.play(Write(t), run_time=2)
