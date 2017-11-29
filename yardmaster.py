#!/usr/bin/python

import RPi.GPIO as GPIO
import pygame, sys, random, math
from pygame.locals import *


WHITE       = ( 255, 255, 255 )
BLACK       = (   0,   0,   0 )
RED         = ( 255,   0,   0 )
GREEN       = (   0, 255,   0 )
DARKGREEN   = (   0, 128,   0 )
DARKYELLOW  = ( 128, 128,  64 )
DARKRED     = ( 128,   0,   0 )
DARKGRAY    = (  64,  64,  64 )

BGCOLOUR = BLACK

SHUTDOWN_PIN = 11
NEXT_MOVE_PIN = 12

TYPE = 0
TIME = 1
AM_PM = 2
DESCRIPTION = 3

class Wagon:
    def __init__( self, load, age ):
        self.load = load
        self.age = age
        self.outgoing = False

    def markOutgoing( self ):
        self.outgoing = True

def wagonRemaining( wagon ):
    return not wagon.outgoing

def parseVertex( vertex, game ):
    coords = vertex.split( ',' )
    return (    int( coords[0] ),
                int( coords[1] ) + game.height / 3 + 30 )

class Siding:
    def __init__( self, length, vertices, game ):
        self.length = length
        self.vertices = [   parseVertex( vertex, game ) 
                            for vertex in vertices.split( ';' ) ]
        self.present = 0
        self.wagons = []

    def draw( self, game ):
        pygame.draw.lines( 
            game.surface, 
            WHITE, 
            False, 
            self.vertices, 
            3 )
        left = self.vertices[0][0]
        top = self.vertices[0][1]
        if left < self.vertices[1][0]:
            factor = 1
        else:
            factor= -1
        for wagon in self.wagons:
            if wagon.age == 0:
                colour = DARKGREEN
            elif wagon.outgoing:
                colour = DARKRED
            else:
                colour = DARKYELLOW
            (width, height) = game.font.size( wagon.load )
            if factor < 0:
                left = left - width
                width = 10
            else:
                width = width + 10
            game.drawTextLine( 
                wagon.load,
                colour,
                left,
                top )
            left = left + width * factor

    def ageWagons( self ):
        for wagon in self.wagons:
            incr = random.randint( 1, 5 )
            wagon.age = wagon.age + incr

    def selectOutgoing( self, oldest, trainLength ):
        for wagon in self.wagons:
            if len( oldest ) < trainLength:
                oldest.append( wagon )
            else:
                minAge = 0
                youngest = oldest[0]
                for candidate in oldest:
                    if candidate.age < youngest.age:
                        youngest = candidate
                if wagon.age > youngest.age:
                    oldest.remove( youngest )
                    oldest.append( wagon )

    def removeOutgoing( self ):
        self.wagons = filter( wagonRemaining, self.wagons )
                        
class Game:
    def __init__( self, baseName ):
        self.clock = pygame.time.Clock()
        self.moves = []
        self.loads = []
        self.sidings = []
        self.trainLength = 1
        self.lastMovePress = pygame.time.get_ticks()
        self.moveIndex = 0
        self.moveTime = 0
        self.time = 0
        self.surface = pygame.display.set_mode( ( 0, 0 ), pygame.FULLSCREEN )
        self.width = self.surface.get_width()
        self.height = self.surface.get_height()
        #self.font = pygame.font.SysFont( 'freesansbold', 18, True )
        self.font = pygame.font.Font( 'freesansbold.ttf', 18 )
        pygame.display.set_caption( 'Yardmaster' )
        self.loadWTT( baseName )
        self.loadLayout( baseName )
        self.loadConfig( baseName )
        self.nextMoveTime()
        self.dealCards( self.initialWagonCount )
#        self.dialog( [ 'Press any key to begin' ] )

    def loadWTT( self, baseName ):
        f = open( baseName + ".wtt" )
        self.moves = f.readlines()
        f.close()

    def loadLayout( self, baseName ):
        f = open( baseName + ".layout" )
        for line in f:
            line = line.strip()
            if line != "":
                (length,vertices) = line.split( '/' )
                self.sidings.append( 
                    Siding( int( length ), vertices, self ) )
        f.close()

    def loadConfig( self, baseName ):
        f = open( baseName + ".config" )
        for line in f:
            line = line.strip()
            if line != "":
                (cmd,value,text) = line.split( '/' )
                if cmd == 't':
                    self.trainLength = int( value )
                elif cmd == 'i':
                    self.initialWagonCount = int( value )
                else:
                    for idx in range( 0, int( value ) ):
                        self.loads.append( text )
        f.close()

    def dialog( self, text ):
        lines = map( 
                    lambda line: self.font.render( line, True, DARKGRAY ),
                    text )
        rects = map(
                    lambda line: line.get_rect(),
                    lines )
        total_height = reduce(
                        lambda total, rect: total + rect.height,
                        rects,
                        0 )
        vcenter = ( self.height / 2 ) - ( total_height / 2 )
        for idx in range( 0, len( lines ) ):
            rects[idx].center = ( self.width / 2, vcenter )
            vcenter += rects[idx].height
            self.surface.blit( lines[idx], rects[idx] )
        pygame.display.update()
        pygame.event.get( KEYUP )
        pygame.time.wait( 500 )
        res = 0 
        while res == 0:
            for event in  pygame.event.get():
                if event.type == QUIT:
                    res = 'q'
                elif event.type == KEYUP:
                    res = event.key
        return res

    def start( self ):
        self.fps = 5
        self.surface.fill( BGCOLOUR )

    def nextMoveTime( self ):
        if self.moveIndex < len( self.moves ):
            move = self.moves[ self.moveIndex ].strip()
            if move != "":
                fields = move.split( '/' )
                time = fields[TIME]
                am_pm = fields[AM_PM]
                (hour,minute) = map( int, time.split( ':' ) )
                if hour == 12:
                    hour = 0
                if am_pm == "pm":
                    hour = hour + 12
                self.moveTime = hour * 60 + minute
            else:
                self.moveTime = 0

    def dealCards( self, trainLength ):
        for wIdx in range( 0, trainLength ):
            wagon = Wagon( random.choice( self.loads ), 0 ) 
            allocated = False
            while not allocated:
                sIdx = random.randint( 0, len( self.sidings ) - 1 )
                siding = self.sidings[ sIdx ]
                if siding.present < siding.length:
                    allocated = True
                    siding.wagons.append( wagon )

    def selectOutgoing( self ):
        oldest = []
        for siding in self.sidings:
            siding.selectOutgoing( oldest, self.trainLength ) 
        for wagon in oldest:
            wagon.markOutgoing()

    def ageWagons( self ):
        for siding in self.sidings:
            siding.ageWagons() 
    
    def removeOutgoing( self ):
        for siding in self.sidings:
            siding.removeOutgoing() 

    def checkShutdownButton( self ):
        return not GPIO.input( SHUTDOWN_PIN )

    def handleNextMoveButton( self ):
        pressed = not GPIO.input( NEXT_MOVE_PIN )
        if pressed:
            now = pygame.time.get_ticks()
            if now - self.lastMovePress > 1000:
                self.moveIndex = self.moveIndex + 1
                self.lastMovePress = now
                self.nextMoveTime()
                if self.moveIndex < len( self.moves ):
                    move = self.moves[ self.moveIndex ].strip()
                else:
                    move = ""
                if move != "":
                   moveType = move.split( '/' )[ TYPE ] 
                   if moveType == '-': 
                       self.removeOutgoing()
                   self.ageWagons()
                   if moveType == '+':
                       self.selectOutgoing()
                       self.dealCards( self.trainLength )
                   else:
                       self.train = []

    def drawClock( self, moveIndex ):
        clockSize = ( self.height / 6 ) - 10 
        clockCenter = ( self.height / 6, self.height / 6 )
        clockTime = self.time % 720
        hourRad = float( clockTime ) / 360  * math.pi
        minRad = float( clockTime % 60 ) / 30 * math.pi
        hourHandLength = clockSize - 30
        minHandLength = clockSize - 15
        hourPos = (
            clockCenter[0] + math.sin( hourRad ) * hourHandLength,
            clockCenter[1] - math.cos( hourRad ) * hourHandLength )
        minPos = (
            clockCenter[0] + math.sin( minRad ) * minHandLength,
            clockCenter[1] - math.cos( minRad ) * minHandLength )

        pygame.draw.circle(
            self.surface,
            WHITE,
            clockCenter,
            clockSize )
        pygame.draw.circle(
            self.surface,
            BLACK,
            clockCenter,
            clockSize - 2,
            2 )
        for h in range( 12 ):
            dotRad = float( h ) / 6 * math.pi
            dotRadius = clockSize - 5
            dotPos = (
                        int( clockCenter[0] + math.sin( dotRad ) * dotRadius ),
                        int( clockCenter[1] - math.cos( dotRad ) * dotRadius ) )
            pygame.draw.circle(
                self.surface,
                BLACK,
                dotPos,
                4 )

        pygame.draw.line(
            self.surface,
            BLACK,
            clockCenter,
            hourPos,
            4 )
        pygame.draw.line(
            self.surface,
            BLACK,
            clockCenter,
            minPos )

        self.drawTextLine( 
            "t={}, ct={}".format( self.time, self.moveTime ),
            WHITE,
            10,
            self.height / 3 + 10 )

    def drawTextLine( self, text, colour, left, top ):
        block = self.font.render( text, True, colour )
        blockRect = block.get_rect()
        blockRect.topleft = ( left, top )
        self.surface.blit( block, blockRect )

    def drawText( self, text, colour, left, top ):
        words = text.split()
        line = ""
        for idx in range( 0, len( words ) ):
            test = line + ' ' + words[ idx ]
            (width, height) = self.font.size( test )
            if left + width > self.width:
                self.drawTextLine( line, colour, left, top )
                line = ' ' + words[ idx ]
                top = top + self.font.get_linesize()
            else:
                line = test
        if line != "":
            self.drawTextLine( line, colour, left, top )

    def drawLine( self, moveIndex, colour, slot ):
        move = self.moves[ moveIndex ].strip()
        if move != "":
            (newCards,time,ampm,description) = move.split( '/' ) 
            self.drawTextLine( 
                time, 
                colour, 
                self.height / 3, 
                ( self.height / 9 ) * slot )
            self.drawTextLine( 
                ampm, 
                colour, 
                self.height / 3 + 40,
                ( self.height / 9 ) * slot )
            self.drawText( 
                description, 
                colour, 
                self.height / 3 + 75, 
                ( self.height / 9 ) * slot )

    def drawBoard( self ):
        left = 0
        self.surface.fill( BGCOLOUR )
        self.drawClock( self.moveIndex )
        if self.moveIndex > 0:
            self.drawLine( self.moveIndex - 1, DARKGRAY, 0 )
        self.drawLine( self.moveIndex, WHITE, 1 )
        if ( self.moveIndex + 1 ) < len( self.moves ):
            self.drawLine( self.moveIndex + 1, DARKGRAY, 2 )
        pygame.draw.line(
            self.surface,
            WHITE,
            ( 5, self.height / 3 ),
            ( self.width - 5, self.height / 3 ) )
        for siding in self.sidings:
            siding.draw( self )


    def runGame( self ):
        done = False
        while not done:
            done = self.checkShutdownButton()
            self.handleNextMoveButton()
            if self.moveIndex >= len( self.moves ):
                self.moveIndex = 0
                self.time = 0
            else:
                if self.time < self.moveTime:
                    self.time = self.time + 1
                self.drawBoard()
                pygame.display.update()
                self.clock.tick( self.fps )

def main():
    GPIO.setmode( GPIO.BOARD )
    GPIO.setup( SHUTDOWN_PIN, GPIO.IN )
    GPIO.setup( NEXT_MOVE_PIN, GPIO.IN )
    pygame.init()

    game = Game( sys.argv[1] )
    game.start()
    game.runGame()

    pygame.quit()

if __name__ == '__main__':
    main()

