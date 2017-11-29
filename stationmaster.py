#!/usr/bin/python

import RPi.GPIO as GPIO
import pygame, sys, random, math
from pygame.locals import *


WHITE       = ( 255, 255, 255 )
BLACK       = (   0,   0,   0 )
RED         = ( 255,   0,   0 )
GREEN       = (   0, 255,   0 )
DARKGREEN   = (   0, 128,   0 )
LIGHTGREEN  = (   0, 164,   0 )
DARKYELLOW  = ( 128, 128,  64 )
LIGHTYELLOW = ( 164, 164, 128 )
DARKRED     = ( 164,   0,   0 )
DARKGRAY    = (  96,  96,  96 )

BGCOLOUR = BLACK

MAX_WAGON_WIDTH = 50
WAGON_GAP = 5

PREV_MOVE_PIN = int( 11 ) #blue
NEXT_MOVE_PIN = int( 12 ) #green
WAGON_SELECT_PIN = int( 13 ) #yellow
WAGON_CHANGE_PIN = int( 16 ) #white
SHUTDOWN_PIN = int( 15 ) #red

TYPE = 0
TIME = 1
AM_PM = 2
DESCRIPTION = 3

def wagonOutgoing( wagon ):
    return wagon.outgoing

def wagonRemaining( wagon ):
    return not wagon.outgoing

def wagonState( wagon ):
    return str( wagon.wagonType ) + ',' \
        +  str( wagon.age ) + ',' \
        +  str( wagon.outgoing )

def wagonLoad( wagonState ):
    fields = wagonState.split( ',' )
    wagon = Wagon( fields[0] )
    wagon.age = int( fields[1] )
    wagon.outgoing = fields[2] == "True"
    return wagon

def parseVertex( vertex, game ):
    coords = vertex.split( ',' )
    return (    int( coords[0] ),
                int( coords[1] ) + game.height / 3 + 10 )

def incrementIndex( currentValue, limit ):
    newValue = currentValue + 1
    if newValue >= limit:
        newValue = 0
    return newValue

class Button:
    def __init__( self, pin, minRepeatMS ):
        self.pin = pin
        self.minRepeatMS = minRepeatMS
        self.lastPress = pygame.time.get_ticks()
        GPIO.setup( pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN )
        GPIO.add_event_detect( 
            pin,
            GPIO.RISING )

    def pressed( self ):
        pressed = False
        if GPIO.input( self.pin ) or GPIO.event_detected( self.pin ):
            now = pygame.time.get_ticks()
            if now - self.lastPress > self.minRepeatMS:
                self.lastPress = now
                pressed = True
        return pressed

class Wagon:
    def __init__( self, wagonType ):
        self.wagonType = int( wagonType )
        self.age = 0 
        self.outgoing = False
        self.selected = False

    def markOutgoing( self ):
        self.outgoing = True

    def text( self, wagonTypes ):
        if self.wagonType < len( wagonTypes ):
            val = wagonTypes[ self.wagonType ]
        else:
            val = '?'
        return val

    def draw( self, left, top, width, game ):
        if self.age == 0:
            colour = DARKGREEN
        elif self.outgoing:
            colour = DARKRED
        else:
            colour = DARKYELLOW
        top = top - game.wagonFont.get_linesize()
        height = game.wagonFont.get_linesize() + game.wagonFont.get_height()
        text = self.text( game.wagonTypes )
        pygame.draw.rect(
            game.surface,
            colour,
            Rect( left, top, width, height ),
            1 )
        if width < 0:
            left = left + width
            space = -WAGON_GAP
        else:
            space = width + WAGON_GAP
        game.drawText( 
            text,
            colour,
            game.wagonFont,
            left,
            top,
            math.fabs( width ) )
        left = left + space
        return left

    def drawSpare( self, left, top, colour, game ):
        text = self.text( game.wagonTypes )
        (width, height) = game.wagonFont.size( text )
        weight = 1
        if game.selectedWagon() == self:
            weight = 2
        game.drawTextLine( 
            text,
            colour,
            game.wagonFont,
            left,
            top )
        pygame.draw.rect(
            game.surface,
            colour,
            Rect( left, top, width, height ),
            weight )
        return (width,height + 5)

class Siding:
    def __init__( self, length, vertices, game ):
        self.length = length
        self.vertices = [   parseVertex( vertex, game ) 
                            for vertex in vertices.split( ';' ) ]
        self.displayLength = math.fabs(
                                self.vertices[-1][0] 
                                - self.vertices[0][0] )
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
        if self.length > 0:
            wagonWidth = ( self.displayLength / self.length ) - WAGON_GAP
            if wagonWidth > MAX_WAGON_WIDTH:
                wagonWidth = MAX_WAGON_WIDTH
            if left > self.vertices[1][0]:
                wagonWidth = -wagonWidth
            for wagon in self.wagons:
                left = wagon.draw( left, top, wagonWidth, game )

    def ageWagons( self ):
        for wagon in self.wagons:
            incr = random.randint( 1, 5 )
            wagon.age = wagon.age + incr

    def selectOutgoing( self, oldest, trainLength ):
        for wagon in self.wagons:
            if len( oldest ) < trainLength:
                oldest.append( wagon )
            else:
                youngest = oldest[0]
                for candidate in oldest:
                    if candidate.age < youngest.age:
                        youngest = candidate
                if wagon.age > youngest.age:
                    oldest.remove( youngest )
                    oldest.append( wagon )

    def transferOutgoing( self, rake ):
        rake.extend( filter( wagonOutgoing, self.wagons ) )
        self.wagons = filter( wagonRemaining, self.wagons )

    def save( self, f ):
        f.write( "s/" )
        f.write( "/".join( map( wagonState, self.wagons ) ) + "\n"  )

    def load( self, wagonStates ):
        self.wagons = map( wagonLoad, wagonStates )

class Game:
    def __init__( self, baseName ):
        self.baseName = baseName
        self.clock = pygame.time.Clock()
        self.moves = []
        self.wagonTypes = []
        self.rakes = []
        self.nextRake = 0
        self.selection = ()
        self.sidings = []
        self.trainLength = 1
        self.lastMoveButton = Button( PREV_MOVE_PIN, 1000 ) 
        self.nextMoveButton = Button( NEXT_MOVE_PIN, 1000 )
        self.wagonSelectButton = Button( WAGON_SELECT_PIN, 500 )
        self.wagonChangeButton = Button( WAGON_CHANGE_PIN, 500 )
        self.shutdownButton = Button( SHUTDOWN_PIN, 0 )
        self.moveIndex = 0
        self.moveTime = 0
        self.time = 0
        self.surface = pygame.display.set_mode( ( 0, 0 ), pygame.FULLSCREEN )
        self.width = self.surface.get_width()
        self.height = self.surface.get_height()
        self.font = pygame.font.Font( 'freesansbold.ttf', 18 )
        self.wagonFont = pygame.font.Font( 'freesansbold.ttf', 16 )
        pygame.display.set_caption( 'Stationmaster' )
        self.loadWTT( baseName )
        self.loadLayout( baseName )
        self.loadState( baseName )
        self.nextMoveTime()

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

    def loadState( self, baseName ):
        try:
            state = open( baseName + ".state" )
        except:
            state = None

        config = open( baseName + ".config" )
        for line in config:
            line = line.strip()
            if line != "":
                fields = line.split( '/' )
                if fields[0] == 'n':
                    self.trainLength = int( fields[1] )
                elif fields[0] == 'w':
                    self.wagonTypes = fields[1:]
                    self.wagonTypes.append( "" )
                elif state == None:
                    if fields[0] == 'r':
                        self.rakes.append( 
                            map( Wagon, fields[1:] ) )
                    elif fields[0] == 'i':
                        self.allocateWagons( 
                            map( Wagon, fields[1:] ) )
        config.close()

        if state != None:
            sidingIter = self.sidings.__iter__()
            for line in state:
                line = line.strip()
                fields = line.split( '/' )
                if fields[0] == 'm':
                    self.moveIndex = int( fields[1] )
                elif fields[0] == 'r':
                    if fields[1] != '' :
                        self.rakes.append(
                            map( wagonLoad, fields[1:] ) )
                elif fields[0] == 's':
                    siding = sidingIter.next()
                    if fields[1] != '':
                        siding.load( fields[1:] )
            state.close()

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

    def allocateWagons( self, train ):
        for wagon in train:
            allocated = False
            while not allocated:
                sIdx = random.randint( 0, len( self.sidings ) - 1 )
                siding = self.sidings[ sIdx ]
                if len( siding.wagons ) < siding.length:
                    allocated = True
                    siding.wagons.append( wagon )

    def handleShutdownButton( self ):
        f = open( self.baseName + ".state", "w" )
        f.write( "m/{}\n".format( self.moveIndex ) )
        for siding in self.sidings:
            siding.save( f )
        for rake in self.rakes:
            f.write( "r/" )
            f.write( "/".join( map( wagonState, rake ) ) + "\n"  )
        f.close()
        
    def selectOutgoing( self ):
        oldest = []
        for siding in self.sidings:
            siding.selectOutgoing( oldest, self.trainLength ) 
        for wagon in oldest:
            wagon.markOutgoing()

    def ageWagons( self ):
        for siding in self.sidings:
            siding.ageWagons() 
    
    def transferOutgoing( self, rake ):
        for siding in self.sidings:
            siding.transferOutgoing( rake ) 
        for wagon in rake:
            wagon.age = 0
            wagon.outgoing = False

    def handleNextMoveButton( self ):
        self.moveIndex = incrementIndex( self.moveIndex, len( self.moves ) )
        if self.moveIndex == 0:
            self.time = 0
        self.nextMoveTime()
        move = self.moves[ self.moveIndex ].strip()
        if move != "":
            rake = self.rakes[ self.nextRake ] 
            moveType = move.split( '/' )[ TYPE ] 
            if moveType == '-': 
                self.transferOutgoing( rake )
                self.nextRake = incrementIndex( 
                                    self.nextRake,
                                    len( self.rakes ) )
            self.ageWagons()
            if moveType == '+':
                self.selectOutgoing()
                self.allocateWagons( rake )
                rake[:] = []

    def selectedWagon( self ):
        wagon = None
        if len( self.selection ) > 0:
            rake = self.rakes[ self.selection[0] ]
            wagon = rake[ self.selection[1] ]
        return wagon

    def handleWagonSelectButton( self ):
        currentWagon = self.selectedWagon()
        if currentWagon != None \
        and currentWagon.wagonType == len( self.wagonTypes ) - 1:
            self.rakes[ self.selection[0] ].remove( currentWagon )
            self.selection = ()
        else:
            if len( self.selection ) == 0:
                self.selection = ( 0, 0 )
            else:
                rake = self.rakes[ self.selection[0] ]
                if self.selection[1] < len( rake ) - 1:
                    self.selection = (  self.selection[0],
                                        self.selection[1] + 1 )
                else:
                    if self.selection[0] < len( self.rakes ) - 1:
                        self.selection = (  self.selection[0] + 1,
                                            0 )
                    else:
                        self.selection = ()

    def handleWagonChangeButton( self ):
        wagon = self.selectedWagon()
        if wagon != None:
            wagon.wagonType = incrementIndex( 
                                wagon.wagonType,
                                len( self.wagonTypes ) )

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

    def drawTextLine( self, text, colour, font, left, top ):
        block = font.render( text, True, colour )
        blockRect = block.get_rect()
        blockRect.topleft = ( left, top )
        self.surface.blit( block, blockRect )

    def drawText( self, text, colour, font, left, top, maxWidth ):
        words = text.split()
        line = ""
        for idx in range( 0, len( words ) ):
            test = line + ' ' + words[ idx ]
            (width, height) = font.size( test )
            if left + width > maxWidth:
                if line != "":
                    self.drawTextLine( line, colour, font, left, top )
                    line = ' ' + words[ idx ]
                else:
                    self.drawTextLine( words[ idx ], colour, font, left, top )
                top = top + font.get_linesize()
            else:
                line = test
        if line != "":
            self.drawTextLine( line, colour, font, left, top )

    def drawMove( self, moveIndex, colour, slot ):
        move = self.moves[ moveIndex ].strip()
        if move != "":
            (newCards,time,ampm,description) = move.split( '/' ) 
            self.drawTextLine( 
                time, 
                colour,
                self.font,
                self.height / 3, 
                ( self.height / 9 ) * slot )
            self.drawTextLine( 
                ampm, 
                colour,
                self.font,
                self.height / 3 + 40,
                ( self.height / 9 ) * slot )
            self.drawText( 
                description, 
                colour,
                self.font,
                self.height / 3 + 75, 
                ( self.height / 9 ) * slot,
                self.width )

    def drawRakes( self, top ):
        for rake in self.rakes:
            height = 0
            left = 10
            for wagon in rake:
                if rake == self.rakes[ self.nextRake ]:
                    colour = LIGHTYELLOW
                else:
                    colour = DARKGRAY
                (width,height) = wagon.drawSpare( left, top, colour, self )
                left = left + width + 10 
            top = top + height + 10

    def drawBoard( self ):
        left = 0
        self.surface.fill( BGCOLOUR )
        self.drawClock( self.moveIndex )
        if self.moveIndex > 0:
            self.drawMove( self.moveIndex - 1, DARKGRAY, 0 )
        self.drawMove( self.moveIndex, WHITE, 1 )
        if ( self.moveIndex + 1 ) < len( self.moves ):
            self.drawMove( self.moveIndex + 1, DARKGRAY, 2 )
        pygame.draw.line(
            self.surface,
            WHITE,
            ( 5, self.height / 3 ),
            ( self.width - 5, self.height / 3 ) )
        for siding in self.sidings:
            siding.draw( self )
        top = self.height / 6 * 5
        pygame.draw.line(
            self.surface,
            WHITE,
            ( 5, top ),
            ( self.width - 5, top ) )
        self.drawRakes( top + 10 )

    def runGame( self ):
        done = False
        while not done:
            if self.shutdownButton.pressed():
                self.handleShutdownButton()
                done = True
            elif self.nextMoveButton.pressed():
                self.handleNextMoveButton()
            elif self.wagonSelectButton.pressed():
                self.handleWagonSelectButton()
            elif self.wagonChangeButton.pressed():
                self.handleWagonChangeButton()

            if self.time < self.moveTime:
                self.time = self.time + 1
            self.drawBoard()
            pygame.display.update()
            self.clock.tick( self.fps )

def main():
    GPIO.setmode( GPIO.BOARD )

    pygame.init()
    pygame.mouse.set_visible( False )

    game = Game( sys.argv[1] )
    game.start()
    game.runGame()

    pygame.quit()

if __name__ == '__main__':
    main()

