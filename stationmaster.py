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

#unused = int( 11 ) #blue
EXIT_PIN = int( 15 ) #red
WAGON_CHANGE_PIN = int( 16 ) #white
WAGON_SELECT_PIN = int( 13 ) #yellow
NEXT_MOVE_PIN = int( 22 ) #green

TYPE = 0
TIME = 1
AM_PM = 2
DESCRIPTION = 3

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

class WagonType:
    def __init__( self, wagonDefn ):
        fields = wagonDefn.split( ',' )
        self.name = fields[0]
        self.length = float( fields[1] )

class Wagon:
    def __init__( self, wagonState ):
        fields = wagonState.split( ',' )
        self.wagonType = int( fields[0] )
        if len( fields ) > 1:
            self.age = int( fields[1] )
        else:
            self.age = 0
        if len( fields ) > 2:
            self.outgoing = fields[2] == "True"
        else:
            self.outgoing = False
        self.selected = False

    def reset( self ):
        self.age = 0
        self.outgoing = False

    def incrAge( self ):
        incr = random.randint( 1, 5 )
        self.age = self.age + incr

    def markOutgoing( self ):
        self.outgoing = True

    def isOutgoing( self ):
        return self.outgoing

    def text( self, wagonTypes ):
        if self.wagonType < len( wagonTypes ):
            val = wagonTypes[ self.wagonType ].name
        else:
            val = '?'
        return val

    def length( self, wagonTypes ):
        if self.wagonType < len( wagonTypes ):
            val = wagonTypes[ self.wagonType ].length
        else:
            val = 1
        return val

    def width( self, baseWidth, wagonTypes ):
        return self.length( wagonTypes ) * baseWidth

    def state( self ):
        return str( self.wagonType ) + ',' \
            +  str( self.age ) + ',' \
            +  str( self.outgoing )

    def draw( self, left, top, baseWidth, game ):
        if self.age == 0:
            colour = DARKGREEN
        elif self.outgoing:
            colour = DARKRED
        else:
            colour = DARKYELLOW
        top = top - game.wagonFont.get_linesize()
        height = game.wagonFont.get_linesize() + game.wagonFont.get_height()
        text = self.text( game.wagonTypes )
        width = self.width( baseWidth, game.wagonTypes )
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
    def __init__( self, length, wagonTypes, vertices, game ):
        self.length = length
        if wagonTypes != '':
            self.wagonTypes = [ int( wt ) for wt in wagonTypes.split( ',' ) ]
        else:
            self.wagonTypes = []
        self.vertices = [   game.parseVertex( vertex )
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
        [ wagon.incrAge() for wagon in self.wagons ]

    def selectOutgoing( self, oldest, trainLength, wagonTypes ):
        def sumLengths( lhs, rhs ):
            return lhs + rhs.length( wagonTypes )

        def removeYoungest( oldest ):
            youngest = oldest[0]
            for candidate in oldest:
                if candidate.age < youngest.age:
                    youngest = candidate
            oldest.remove( youngest )

        for wagon in self.wagons:
            oldest.append( wagon )
            while reduce( sumLengths, oldest, 0 ) > trainLength:
                removeYoungest( oldest )

    def transferOutgoing( self, rake ):
        rake.extend( [ w for w in self.wagons if w.isOutgoing() ] )
        self.wagons = [ w for w in self.wagons if not w.isOutgoing() ]

    def accepts( self, wagon ):
        return wagon.wagonType in self.wagonTypes

    def save( self, f ):
        f.write( "s/" )
        f.write( "/".join( map( Wagon.state, self.wagons ) ) + "\n" )

    def load( self, wagonStates ):
        self.wagons = map( Wagon, wagonStates )

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
        self.nextMoveButton = Button( NEXT_MOVE_PIN, 1000 )
        self.wagonSelectButton = Button( WAGON_SELECT_PIN, 500 )
        self.wagonChangeButton = Button( WAGON_CHANGE_PIN, 500 )
        self.exitButton = Button( EXIT_PIN, 0 )
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

    def parseVertex( self, vertex ):
        coords = vertex.split( ',' )
        return (    int( coords[0] ),
                    int( coords[1] ) + self.height / 3 + 10 )

    def loadWTT( self, baseName ):
        f = open( baseName + ".wtt" )
        self.moves = f.readlines()
        f.close()

    def loadLayout( self, baseName ):
        f = open( baseName + ".layout" )
        for line in f:
            line = line.strip()
            if line != "" and line[0] != '#':
                (length,types,vertices) = line.split( '/' )
                self.sidings.append(
                    Siding( int( length ), types, vertices, self ) )
        f.close()

    def loadState( self, baseName ):
        try:
            state = open( baseName + ".state" )
        except:
            state = None

        config = open( baseName + ".config" )
        for line in config:
            line = line.strip()
            if line != "" and line[0] != '#':
                fields = line.split( '/' )
                if fields[0] == 'n':
                    self.trainLength = int( fields[1] )
                elif fields[0] == 'w':
                    self.wagonTypes = map( WagonType, fields[1:] )
                    self.wagonTypes.append( WagonType( ",0" ) )
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
                    if fields[1] != '':
                        wagons = map( Wagon, fields[1:] )
                    else:
                        wagons = []
                    self.rakes.append( wagons )
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
            possibilities = [ siding    for siding in self.sidings
                                        if siding.accepts( wagon ) ]
            while not allocated and len( possibilities ) > 0:
                sIdx = random.randint( 0, len( possibilities ) - 1 )
                siding = possibilities[ sIdx ]
                if len( siding.wagons ) < siding.length:
                    allocated = True
                    siding.wagons.append( wagon )
                else:
                    possibilities.remove( siding )

            if not allocated:
                possibilities = [ siding    for siding in self.sidings
                                            if siding.accepts( wagon ) ]
                possibilities[0].wagons.append( wagon )


    def handleExitButton( self ):
        f = open( self.baseName + ".state", "w" )
        f.write( "m/{}\n".format( self.moveIndex ) )
        [ siding.save( f ) for siding in self.sidings ]
        nextRake = self.nextRake
        allRakesWritten = False
        while not allRakesWritten:
            rake = self.rakes[ nextRake ]
            f.write( "r/" )
            f.write( "/".join( map( Wagon.state, rake ) ) + "\n"  )
            nextRake = incrementIndex( nextRake, len( self.rakes ) )
            allRakesWritten = nextRake == self.nextRake
        f.close()

    def selectOutgoing( self ):
        oldest = []
        [ siding.selectOutgoing( oldest, self.trainLength, self.wagonTypes )
            for siding in self.sidings ]
        [ wagon.markOutgoing() for wagon in oldest ]

    def ageWagons( self ):
        [ siding.ageWagons() for siding in self.sidings ]

    def transferOutgoing( self, rake ):
        [ siding.transferOutgoing( rake ) for siding in self.sidings ]
        [ wagon.reset() for wagon in rake ]

    def removeDepartedWagons( self ):
        move = self.moves[ self.moveIndex ].strip()
        if move != "":
            moveType = move.split( '/' )[ TYPE ]
            if moveType == '-':
                rake = self.rakes[ self.nextRake ]
                self.transferOutgoing( rake )
                self.nextRake = incrementIndex(
                                    self.nextRake,
                                    len( self.rakes ) )

    def handleNextMoveButton( self ):
        self.removeDepartedWagons()
        self.ageWagons()
        self.moveIndex = incrementIndex( self.moveIndex, len( self.moves ) )
        if self.moveIndex == 0:
            self.time = 0
        self.nextMoveTime()
        move = self.moves[ self.moveIndex ].strip()
        if move != "":
            rake = self.rakes[ self.nextRake ]
            moveType = move.split( '/' )[ TYPE ]
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
            height = self.wagonFont.get_linesize()
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
        [ siding.draw( self ) for siding in self.sidings ]
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
            if self.exitButton.pressed():
                self.handleExitButton()
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
