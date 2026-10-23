import unittest
from adapters.blender.structure_terrain import below_structures

class StructuralTerrainTests(unittest.TestCase):
    def test_every_tread_and_landing_remains_exposed_across_width(self):
        item={'kind':'terraced_foundation','center':[7,18],'size':[10,12],'base_z':.135,'rise':2.7,'stair_run':14}
        start=-2
        for step in range(18):
            for fraction in [.05,.5,.95]:
                y=start+(step+fraction)*14/18
                top=.135+2.7*(step+1)/18
                for x in [2,4,7,10,12]:
                    self.assertLess(below_structures([item],x,y,20),top-.1)
        self.assertLess(below_structures([item],7,23,20),2.835)
        self.assertEqual(below_structures([item],20,6,20),20)

    def test_excavation_never_raises_lower_terrain(self):
        item={'kind':'terraced_foundation','center':[0,0],'size':[4,6],'base_z':0,'rise':1.2,'stair_run':6}
        self.assertEqual(below_structures([item],0,0,-2),-2)
        self.assertEqual(below_structures([],0,0,3),3)
