import java.net.http.{HttpClient, HttpRequest, HttpResponse}
import java.net.URI
import java.net.URLEncoder
import java.nio.charset.StandardCharsets
import play.api.libs.json.Json

object KeycloakTokenProvider {
  
  case class TokenResponse(access_token: String, expires_in: Int)
  
  def getAccessToken(
    keycloakUrl: String,
    realm: String,
    clientId: String,
    clientSecret: String,
    username: String,
    password: String
  ): String = {
    
    val tokenEndpoint = s"$keycloakUrl/realms/$realm/protocol/openid-connect/token"
    
    val formData = Map(
      "grant_type" -> "password",
      "client_id" -> clientId,
      "client_secret" -> clientSecret,
      "username" -> username,
      "password" -> password
    )
    
    val formBody = formData.map { case (key, value) =>
      s"${URLEncoder.encode(key, StandardCharsets.UTF_8)}=${URLEncoder.encode(value, StandardCharsets.UTF_8)}"
    }.mkString("&")
    
    val client = HttpClient.newHttpClient()
    val request = HttpRequest.newBuilder()
      .uri(URI.create(tokenEndpoint))
      .header("Content-Type", "application/x-www-form-urlencoded")
      .POST(HttpRequest.BodyPublishers.ofString(formBody))
      .build()
    
    val response = client.send(request, HttpResponse.BodyHandlers.ofString())
    
    if (response.statusCode() == 200) {
      val json = Json.parse(response.body())
      (json \ "access_token").as[String]
    } else {
      throw new RuntimeException(s"Failed to get token: ${response.body()}")
    }
  }
