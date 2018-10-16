module Pages.ApiSetup exposing (Msg, update, view)

import Css
import DjangoSend exposing (CSRFToken, post)
import Html exposing (Html)
import Html.Attributes as A
import Html.Events as E
import Http
import Json.Decode as Decode
import Json.Encode as Encode
import Notification as Notif
import Urls


-- Update


type Msg
    = Get
    | Generate
    | Delete
    | ReceiveApiKey (Result Http.Error String)


type alias Props =
    { csrftoken : CSRFToken
    , key : Maybe String
    , notifications : Notif.Notifications
    }


update : Msg -> Props -> ( Maybe String, Notif.Notifications, List (Cmd Msg) )
update msg props =
    case msg of
        Get ->
            ( props.key, props.notifications, [ Http.get Urls.api_setup decodeToken |> Http.send ReceiveApiKey ] )

        Generate ->
            ( props.key, props.notifications, [ genKey props.csrftoken ] )

        Delete ->
            ( props.key, props.notifications, [ delKey props.csrftoken ] )

        ReceiveApiKey (Ok key) ->
            ( Just key, props.notifications, [] )

        ReceiveApiKey (Err _) ->
            ( props.key
            , Notif.addRefreshNotif props.notifications
            , []
            )


genKey : CSRFToken -> Cmd Msg
genKey csrf =
    post csrf Urls.api_setup [ ( "regen", Encode.bool True ) ] decodeToken
        |> Http.send ReceiveApiKey


delKey : CSRFToken -> Cmd Msg
delKey csrf =
    post csrf Urls.api_setup [ ( "delete", Encode.bool True ) ] decodeToken
        |> Http.send ReceiveApiKey


decodeToken : Decode.Decoder String
decodeToken =
    Decode.field "token" Decode.string



-- View


view : Maybe String -> Html Msg
view maybeApiKey =
    case maybeApiKey of
        Nothing ->
            Html.div [ Css.m_4 ]
                [ Html.button
                    [ E.onClick Get
                    , A.id "showKeyButton"
                    , Css.btn
                    , Css.btn_purple
                    ]
                    [ Html.text "Show Key" ]
                ]

        Just apiKey ->
            Html.div [ Css.m_4 ]
                [ Html.p []
                    [ Html.text "For more details and help, please read the "
                    , Html.a [ A.href "https://apostello.readthedocs.io/en/latest/api.html" ] [ Html.text "docs" ]
                    , Html.text "."
                    ]
                , Html.br [] []
                , Html.p [] [ Html.text "API Token" ]
                , Html.pre [ Css.my_2 ] [ Html.text apiKey ]
                , Html.button
                    [ E.onClick Generate
                    , A.id "genKeyButton"
                    , Css.btn
                    , Css.btn_green
                    ]
                    [ Html.text "(Re)Generate Token" ]
                , Html.button
                    [ E.onClick Delete
                    , A.id "delKeyButton"
                    , Css.btn
                    , Css.btn_red
                    ]
                    [ Html.text "Delete Token" ]
                ]
