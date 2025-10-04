import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { decode as decodeBase64 } from "https://deno.land/std@0.200.0/encoding/base64.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";
// Detect file type from filename extension
function getContentType(filename) {
  const ext = filename.toLowerCase().split('.').pop();
  switch(ext){
    case 'pdf':
      return 'application/pdf';
    case 'zip':
      return 'application/zip';
    case 'txt':
      return 'text/plain';
    case 'json':
      return 'application/json';
    case 'csv':
      return 'text/csv';
    default:
      return 'application/octet-stream';
  }
}
Deno.serve(async (req)=>{
  // Only accept POST & JSON
  if (req.method !== "POST" || req.headers.get("content-type") !== "application/json") {
    return new Response("❌ Expected POST with JSON", {
      status: 400
    });
  }
  try {
    const body = await req.json();
    // Create Supabase client (needed for both operations)
    const supabaseUrl = Deno.env.get("SUPABASE_URL");
    const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
    const supabase = createClient(supabaseUrl, supabaseKey);
    // Check if this is a list command
    if (body.cmd === "list") {
      const { data: files, error } = await supabase.storage.from("files").list();
      if (error) {
        console.error("List error:", error);
        return new Response(`❌ Failed to list files: ${error.message}`, {
          status: 500
        });
      }
      return new Response(JSON.stringify({
        message: "Files listed successfully",
        count: files?.length || 0,
        files: files || []
      }), {
        status: 200,
        headers: {
          "Content-Type": "application/json"
        }
      });
    }
    // Check if this is a download command
    if (body.download && typeof body.download === "string") {
      const fileName = body.download;
      const { data: fileData, error } = await supabase.storage.from("files").download(fileName);
      if (error) {
        console.error("Download error:", error);
        return new Response(`❌ Failed to download file: ${error.message}`, {
          status: 404
        });
      }
      if (!fileData) {
        return new Response("❌ File not found", {
          status: 404
        });
      }
      // Get content type from filename
      const contentType = getContentType(fileName);
      // Convert Blob to ArrayBuffer
      const arrayBuffer = await fileData.arrayBuffer();
      return new Response(arrayBuffer, {
        status: 200,
        headers: {
          "Content-Type": contentType,
          "Content-Disposition": `attachment; filename="${fileName}"`,
          "Content-Length": arrayBuffer.byteLength.toString()
        }
      });
    }
    // Otherwise, proceed with file upload
    const { input, filename } = body;
    if (typeof input !== "string") {
      return new Response("❌ 'input' must be a string (base64 encoded)", {
        status: 400
      });
    }
    // Decode base64 to binary data
    let decodedBytes;
    try {
      decodedBytes = decodeBase64(input);
    } catch  {
      return new Response("❌ Invalid base64 string", {
        status: 400
      });
    }
    // Choose filename—either provided or generate one
    const fileName = filename && typeof filename === "string" ? filename : `file_${Date.now()}.bin`;
    // Detect content type from filename
    const contentType = getContentType(fileName);
    // Upload decoded bytes as a file to bucket 'files'
    // Use the raw bytes for binary files (PDF, ZIP) instead of converting to text
    const { data, error } = await supabase.storage.from("files").upload(fileName, new Blob([
      decodedBytes
    ], {
      type: contentType
    }), {
      upsert: true,
      contentType: contentType
    });
    if (error) {
      console.error("Upload error:", error);
      return new Response(`❌ Failed to save file: ${error.message}`, {
        status: 500
      });
    }
    // Get public URL (if bucket is public) or signed URL
    const { data: urlData } = supabase.storage.from("files").getPublicUrl(fileName);
    return new Response(JSON.stringify({
      message: "File uploaded successfully",
      filename: fileName,
      path: data?.path,
      contentType: contentType,
      size: decodedBytes.length,
      publicUrl: urlData?.publicUrl
    }), {
      status: 200,
      headers: {
        "Content-Type": "application/json"
      }
    });
  } catch (err) {
    console.error("Error:", err);
    return new Response(`❌ Bad Request: ${err instanceof Error ? err.message : 'Unknown error'}`, {
      status: 400
    });
  }
});
