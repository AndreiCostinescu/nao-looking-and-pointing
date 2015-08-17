import sys
import time
import math
import numpy
import motion
from naoqi import ALProxy

class NaoGestures():
    def __init__(self):
        """
        Initialize a Nao connection.

        Attempts to connect to a Nao using the IP address contained in local file ip.txt, 
        and will fail if a connection is not available.
        """
        # Get the Nao's IP and port
        ipAdd = None
        port = None
        try:
            ipFile = open("ip.txt")
            lines = ipFile.read().replace("\r", "").split("\n")
            ipAdd = lines[0]
            port = int(lines[1])
        except Exception as e:
            print "Could not open file ip.txt"
            ipAdd = raw_input("Please write Nao's IP address... ")
            port = raw_input("Please write Nao's port... ")

        # Set motionProxy
        try:
            self.motionProxy = ALProxy("ALMotion", ipAdd, port)
        except Exception as e:
            print "Could not create proxy to ALMotion"
            print "Error was: ", e
            sys.exit()

        # Set postureProxy
        try:
            self.postureProxy = ALProxy("ALRobotPosture", ipAdd, port)
        except Exception, e:
            print "Could not create proxy to ALRobotPosture"
            print "Error was: ", e
            sys.exit()

        # Set ttsProxy
        try:
            self.ttsProxy = ALProxy("ALTextToSpeech", ipAdd, port)
        except Exception, e:
            print "Could not create proxy to ALTextToSpeech"
            print "Error was: ", e
            sys.exit()

        # Set constants
        self.torsoHeadOffset = numpy.array([0.0, 
                                            0.0, 
                                            0.1264999955892563])
        self.torsoLShoulderOffset = numpy.array([0.0, 
                                                 0.09000000357627869, 
                                                 0.10599999874830246])
        self.torsoRShoulderOffset = numpy.array([0.0, 
                                                -0.09000000357627869, 
                                                 0.10599999874830246])
        self.lArmInitPos = [0.11841137707233429, 
                            0.13498550653457642, 
                           -0.04563630372285843, 
                           -1.2062638998031616, 
                            0.4280231297016144, 
                            0.03072221577167511]
        self.rArmInitPos = [0.11877211928367615, 
                           -0.13329118490219116, 
                           -0.04420270770788193, 
                            1.2169694900512695, 
                            0.4153063893318176, 
                           -0.012792877852916718]
        self.armLength = 0.22 # in meters, rounded down
        self.frame = motion.FRAME_TORSO
        self.axisMask = 7 # just control position
        self.useSensorValues = False

    def speak(self, text):
        """
        Command the robot to read the provided text out loud.

        Arguments:
        text -- the text for the robot to read

        Returns: none (but causes robot action)
        """

        self.ttsProxy.say(text)

    def doIdleBehaviors(self):
        """
        Perform small life-like idle behaviors by shifting body and head.
        """
        doIdle = True

        self.motionProxy.setStiffnesses("Body", 1.0)

        # Wake up robot
        self.motionProxy.wakeUp()

        # Send robot to standing position
        self.postureProxy.goToPosture("StandInit", 0.5)

        # Enable whole body balancer
        self.motionProxy.wbEnable(True)

        # Legs are constrained fixed
        self.motionProxy.wbFootState("Fixed", "Legs")

        # Constraint blaance motion
        self.motionProxy.sbEnableBalanceConstraint(True, "Legs")

        useSensorValues = False
        frame = motion.FRAME_ROBOT
        effectorList = ["Torso"]

        dy_max = 0.06
        dz_max = 0.06

        startTf = motionProxy.getTransform("Torso", frame, useSensorValues)

        while doIdle:
            # Pick a random distance for hip sway TODO
            dy = dy_max
            dz = dz_max

            # Alternate sides of hip sway
            target1Tf = almath.Transform(startTf)
            target1Tf.r2_c4 += dy
            target1Tf.r3_c4 -= dz

            target2Tf = almath.Transform(startTf)
            target2Tf.r2_c4 -= dy
            target2Tf.r3_c4 -= dz

            pathTorso = []
            for i in range(3):
                pathTorso.append(list(target1Tf.toVector()))
                pathTorso.append(currentTf)
                pathTorso.append(list(target2Tf.toVector()))
                pathTorso.append(currentTf)

            axisMaskList = [almath.AXIS_MASK_ALL]

            timescoef = 0.5
            timesList = [timescoef]

            motionProxy.transformInterpolations(
                    effectorList, frame, pathList, axisMaskList, timesList)


            # TODO TEST THIS!!!

        # Deactivate body and send robot to sitting pose
        self.motionProxy.wbEnable(False)
        self.postureProxy.goToPosture("StandInit", 0.3)
        self.motionProxy.rest()

    def doGesture(self, gestureType, torsoObjectVector):
        self.postureProxy.goToPosture("StandInit", 0.5)
        if gestureType == "none":
            pass
        elif gestureType == "look":
            self.look(torsoObjectVector)
        elif gestureType == "point":
            arm = "LArm" if torsoObjectVector[1] >= 0 else "RArm"
            self.point(arm, torsoObjectVector)
        elif gestureType == "lookandpoint":
            arm = "LArm" if torsoObjectVector[1] >= 0 else "RArm"
            self.lookAndPoint(arm, torsoObjectVector)
        else:
            print "Error: gestureType must be 'none', 'look', 'point', or 'lookandpoint'"
            return
        self.postureProxy.goToPosture("StandInit", 0.5)

    def look(self, torsoObjectVector):
        pitch, yaw = self.getPitchAndYaw(torsoObjectVector)
        sleepTime = 2 # seconds
        self.moveHead(pitch, yaw, sleepTime) # Move head to look
        self.moveHead(0, 0, sleepTime) # Move head back

    def point(self, pointingArm, torsoObjectVector):
        shoulderOffset, initArmPosition = self.setArmVars(pointingArm)
        IKTarget = self.getIKTarget(torsoObjectVector, shoulderOffset)
        sleepTime = 3 # seconds
        self.moveArm(pointingArm, IKTarget, sleepTime) # Move arm to point
        self.moveArm(pointingArm, initArmPosition, sleepTime) # Move arm back

    def lookAndPoint(self, pointingArm, torsoObjectVector):
        pitch, yaw = self.getPitchAndYaw(torsoObjectVector)
        shoulderOffset, initArmPosition = self.setArmVars(pointingArm)
        IKTarget = self.getIKTarget(torsoObjectVector, shoulderOffset)
        sleepTime = 0 # set individual sleep times to 0

        # Move arm and head to gesture
        self.moveArm(pointingArm, IKTarget, sleepTime)
        self.moveHead(pitch, yaw, sleepTime)
        time.sleep(3)

        # Move arm and head back
        self.moveArm(pointingArm, initArmPosition, sleepTime)
        self.moveHead(0, 0, sleepTime)
        time.sleep(3)

    def getPitchAndYaw(self, torsoObjectVector):
        # Get unit vector from head to object
        headObjectVector = torsoObjectVector - self.torsoHeadOffset
        headObjectUnitVector = [x / self.magn(headObjectVector) for x in headObjectVector]

        # Compute pitch and yaw of unit vector
        pitch = -math.asin(headObjectUnitVector[2])
        yaw = math.acos(headObjectUnitVector[0])
        if headObjectUnitVector[1] < 0:
            yaw *= -1
        return pitch, yaw

    def magn(self, v):
        return math.sqrt(v[0]**2 + v[1]**2 + v[2]**2)

    def moveHead(self, pitch, yaw, sleepTime):
        head = ["HeadPitch", "HeadYaw"]
        fractionMaxSpeed = 0.1
        self.motionProxy.setAngles(head, [pitch, yaw], fractionMaxSpeed)
        time.sleep(sleepTime)

    def setArmVars(self, pointingArm):
        shoulderOffset = None
        initArmPosition = None
        if pointingArm == "LArm":
            shoulderOffset = self.torsoLShoulderOffset
            initArmPosition = self.lArmInitPos
        elif pointingArm == "RArm":
            shoulderOffset = self.torsoRShoulderOffset
            initArmPosition = self.rArmInitPos
        else:
            print "ERROR: Must provide point() with LArm or RArm"
            sys.exit(1)
        return shoulderOffset, initArmPosition

    def getIKTarget(self, torsoObjectVector, shoulderOffset):
        # vector from shoulder to object
        shoulderObjectVector = torsoObjectVector - shoulderOffset

        # scale vector by arm length
        shoulderObjectVectorMagn = self.magn(shoulderObjectVector)
        ratio = self.armLength / shoulderObjectVectorMagn
        IKTarget = [x*ratio for x in shoulderObjectVector]

        # get scaled vector in torso coordinate frame
        IKTarget += shoulderOffset
        IKTarget = list(numpy.append(IKTarget, [0.0, 0.0, 0.0]))
        return IKTarget

    def moveArm(self, pointingArm, IKTarget, sleepTime):
        fractionMaxSpeed = 0.9
        self.motionProxy.setPosition(pointingArm, self.frame, IKTarget, fractionMaxSpeed, self.axisMask)
        time.sleep(sleepTime)


    def testMovements(self):
        """ A test function that looks, points, then looks and points, to a hardcoded target. """

        torsoObjectVector = [1.0, -1.0, 1.0]
        self.doGesture("look", torsoObjectVector)
        self.doGesture("point", torsoObjectVector)
        self.doGesture("lookandpoint", torsoObjectVector)

if __name__ == '__main__':
    naoGestures = NaoGestures()
    
