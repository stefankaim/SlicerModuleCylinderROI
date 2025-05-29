import math
import vtk
import qt
import slicer
from slicer.ScriptedLoadableModule import *


class CylinderTransform(ScriptedLoadableModule):
    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        parent.title = "Cylinder Creator"
        parent.categories = ["ROIs"]
        parent.dependencies = []
        parent.contributors = ["Stefan Kaim, Thomas Hofmann"]
        parent.helpText = "Creates Cylindrical SegmentationNodes for each Markup-Point (ListPoint) as a standing Cylinder (in z-direciton)."
        parent.acknowledgementText = "-"


class CylinderTransformWidget(ScriptedLoadableModuleWidget):
    def setup(self):
        ScriptedLoadableModuleWidget.setup(self)

        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(8)

        # Markup Selector
        self.markupSelector = slicer.qMRMLNodeComboBox()
        self.markupSelector.nodeTypes = ["vtkMRMLMarkupsFiducialNode"]
        self.markupSelector.selectNodeUponCreation = True
        self.markupSelector.addEnabled = False
        self.markupSelector.removeEnabled = False
        self.markupSelector.noneEnabled = False
        self.markupSelector.setMRMLScene(slicer.mrmlScene)

        # Radius and Height Spinbox
        self.radiusSpinBox = qt.QDoubleSpinBox()
        self.radiusSpinBox.minimum = 0.1
        self.radiusSpinBox.maximum = 100.0
        self.radiusSpinBox.singleStep = 0.1
        self.radiusSpinBox.value = 5.0

        self.heightSpinBox = qt.QDoubleSpinBox()
        self.heightSpinBox.minimum = 0.1
        self.heightSpinBox.maximum = 500.0
        self.heightSpinBox.singleStep = 1.0
        self.heightSpinBox.value = 20.0

        # Form Layout
        formLayout = qt.QFormLayout()
        formLayout.addRow("Choose Markup Node:", self.markupSelector)
        formLayout.addRow("Cylinder Radius (mm):", self.radiusSpinBox)
        formLayout.addRow("Cylinder Height (mm):", self.heightSpinBox)
        self.layout.addLayout(formLayout)

        # Generate Button
        self.createButton = qt.QPushButton("Create Cylinder SegmentationNodes")
        self.layout.addWidget(self.createButton)
        self.createButton.clicked.connect(self.onCreateButtonClicked)

        self.layout.addStretch(1)

    def onCreateButtonClicked(self):
        markupNode = self.markupSelector.currentNode()
        if not markupNode:
            slicer.util.errorDisplay("Choose a Markup Node!")
            return

        radius = self.radiusSpinBox.value
        height = self.heightSpinBox.value

        numberOfPoints = markupNode.GetNumberOfControlPoints()
        if numberOfPoints < 1:
            slicer.util.errorDisplay("The chosen Markup Node does not contain any Points.")
            return

        createdCount = 0

        for i in range(numberOfPoints):
            # Point-Coordinates
            xyz_current = [0, 0, 0]
            markupNode.GetNthControlPointPosition(i, xyz_current)
            pointName = markupNode.GetNthControlPointLabel(i) or f"Point_{i+1}"

            # Direction - next or default Point
            if i < numberOfPoints - 1:
                xyz_next = [0, 0, 0]
                markupNode.GetNthControlPointPosition(i + 1, xyz_next)
            elif i > 0:
                xyz_next = [0, 0, 0]
                markupNode.GetNthControlPointPosition(i, xyz_next)
            else:
                xyz_next = [xyz_current[0], xyz_current[1], xyz_current[2] + 1]

            direction = [xyz_next[j] - xyz_current[j] for j in range(3)]
            length = math.sqrt(sum([c**2 for c in direction]))
            if length == 0:
                direction = [0, 0, 1]
            else:
                direction = [c / length for c in direction]

            # Cylinder along z
            cylinderSource = vtk.vtkCylinderSource()
            cylinderSource.SetRadius(radius)
            cylinderSource.SetHeight(height)
            cylinderSource.SetResolution(50)
            cylinderSource.Update()
            polydata = cylinderSource.GetOutput()

            # Transformation
            transform = vtk.vtkTransform()
            transform.Translate(*xyz_current)
            transform.RotateX(90)

            # Create TransformNode 
            transformNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLinearTransformNode", f"{pointName}_Transform")
            transformNode.SetMatrixTransformToParent(transform.GetMatrix())

            # Create SegmentationNode for each Point
            segmentationNodeName = f"{pointName}_CylinderROI"
            try:
                segmentationNode = slicer.util.getNode(segmentationNodeName)
            except slicer.util.MRMLNodeNotFoundException:
                segmentationNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLSegmentationNode', segmentationNodeName)
                segmentationNode.CreateDefaultDisplayNodes()

            segmentationNode.SetAndObserveTransformNodeID(transformNode.GetID())

            segmentation = segmentationNode.GetSegmentation()
            segmentation.RemoveAllSegments()

            # Add Segment
            segment = slicer.vtkSegment()
            segment.SetName(pointName)
            segment.AddRepresentation(
                slicer.vtkSegmentationConverter.GetSegmentationClosedSurfaceRepresentationName(),
                polydata
            )
            segmentation.AddSegment(segment)

            segmentationNode.Modified()
            createdCount += 1

        slicer.util.infoDisplay(f"Created {createdCount} SegmentationNode(s).")
