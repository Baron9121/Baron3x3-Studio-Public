import Foundation
import Vision
import AppKit
import CoreImage
import ImageIO
import UniformTypeIdentifiers
// Apple Vision runs locally. Requires macOS 14 or newer.
if CommandLine.arguments.count != 3 {fatalError("Usage: swift cutout.swift input.png output.png")}
let input=URL(fileURLWithPath:CommandLine.arguments[1])
let output=URL(fileURLWithPath:CommandLine.arguments[2])
guard let image=CIImage(contentsOf:input) else {fatalError("Cannot read input")}
if #available(macOS 14.0, *) {
 let handler=VNImageRequestHandler(url:input,options:[:])
 let request=VNGenerateForegroundInstanceMaskRequest()
 try handler.perform([request])
 guard let result=request.results?.first, !result.allInstances.isEmpty else {fatalError("No foreground detected")}
 let buffer=try result.generateScaledMaskForImage(forInstances:result.allInstances,from:handler)
 let mask=CIImage(cvPixelBuffer:buffer)
 let clear=CIImage(color:.clear).cropped(to:image.extent)
 let composited=image.applyingFilter("CIBlendWithMask",parameters:[kCIInputBackgroundImageKey:clear,kCIInputMaskImageKey:mask])
 let context=CIContext()
 guard let cg=context.createCGImage(composited,from:image.extent), let dest=CGImageDestinationCreateWithURL(output as CFURL,UTType.png.identifier as CFString,1,nil) else {fatalError("Cannot write PNG")}
 CGImageDestinationAddImage(dest,cg,nil)
 guard CGImageDestinationFinalize(dest) else {fatalError("PNG write failed")}
} else {fatalError("macOS 14+ is required")}
